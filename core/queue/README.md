# JobQueue Peer RPC 与信号总线

Bot 与 Server 进程共用一套双向 RPC 与信号运行时。数据库中的 Peer Registry（进程实例注册表）
是在线拓扑的权威数据源；进程内的 `Alive` 仅作为同步路由缓存，并通过定期对账保持更新。
任何缺少有效租约的缓存记录均不得视为在线实例。

## 组件与职责

| 文件 | 职责 |
| --- | --- |
| `contracts.py` | 声明稳定的方法名称、调用签名、路由规则与默认超时时间 |
| `rpc.py` | 提供保留 Python 签名的调用代理、参数绑定及处理器自动注册机制 |
| `codec.py` | 按声明类型执行编解码，并复用消息与会话对象的转换器 |
| `base.py` | 管理 Peer 调用、结果关联、并发分发、信号扇出及生命周期 |
| `transport.py` | 定义 `RpcTransport` 协议，并提供基于数据库的任务投递实现 |
| `peer.py` | 管理进程身份、租约目录、目标选择、实例退出清理及信号投递结果 |
| `errors.py` | 定义可跨进程识别的异常类型 |
| `client.py` | 解析平台上下文，自动绑定平台接口，并处理推送、私信等特殊逻辑 |
| `server.py` | 实现消息解析、事件分发、模块查询与钩子调用等服务端接口 |
| `reporting.py` | 提交配置中指定的错误报告，并避免错误报告流程等待自身完成 |

`JobQueuePeersTable` 以 `peer_id` 为主键登记每个进程实例。
`JobQueuesTable` 中的 `target_peer`、`source_peer_id`、`correlation_id`、`message_kind` 与
`claimed_by` 分别记录投递目标、来源实例、关联标识、消息类别及实际领取者。

如需替换普通任务的投递后端，应实现 `send`、`send_many`、`receive`、`responses` 与 `finish`。
如需同时将 Peer Registry 迁移至数据库之外，还必须等价实现租约查询、权威实例发现及实例退出后的
未完成任务终结机制。`PeerSelector` 支持按实例、节点、角色、service 与 capability 的交集筛选目标，
并可显式排除指定实例。

## 实例身份、寻址与发现

每个进程具有两层身份：

- `JobQueueBase.name` 是在每次进程生命周期内生成的唯一 `peer_id`。以该标识投递的任务仅能由对应
  实例领取。注册信息同时包含 `node_id` 与 PID，用于区分多节点、多进程环境中的具体实例。
- `PeerIdentity.service` 是稳定的服务组标识，例如 `Server` 或 `QQ`。同一服务组中的实例共同监听
  该标识，并通过原子 `claim()` 确保每条普通 RPC 仅由一个实例领取，从而实现任播（anycast）负载均衡。

同一 service 表示一组能够相互替代并承接同类任务的实例。节点、PID、capabilities 与自定义 metadata
均独立登记，因此后续可以在不修改 RPC 业务载荷的前提下增加权重、分片或区域等路由约束。
无法相互替代的平台账号应使用不同的 service；如确需归入同一 service，则必须在启用多实例之前
补充能够区分账号或分片的路由条件。

`check_job_queue()` 启动时依次完成以下操作：以 `starting` 状态注册实例、启用实例寻址、切换为
`ready`、读取完整拓扑，并向现有在线实例广播 `peer.ready`。运行期间，每 15 秒续订一次租约，
每 10 秒依据数据库执行一次完整拓扑对账。正常关闭时，实例先通过 `peer.draining` 停止接收新任务，
完成在途任务清理后再广播 `peer.stopped`；异常退出则在 45 秒租约到期后被识别。

保活信息不再定向发送至某个 Server，因此多个 Server 可以依据同一权威注册表获得一致的在线视图。
数据库热重载等维护操作会将实例状态切换为 `maintenance`，并广播 `peer.maintenance`，使该实例暂时退出
稳定路由。连接恢复后，实例重新注册为 `ready` 并广播 `peer.resumed`，从而避免在维护期间接收新消息。

所有生命周期信号均须由其载荷中对应的 `peer_id` 发出，并且仅在信号内容与 Registry 当前状态一致时
更新本地缓存。延迟到达的 `ready`、`resumed` 或 `stopped` 信号不得覆盖更新后的权威状态。

## RPC 调用

```python
from core.queue.contracts import PlatformAPI, ServerAPI

# 等待远端执行完成。成功时返回签名声明的值，失败时抛出 RpcError 子类。
message_ids = await PlatformAPI.send_message(session_info, message, quote=False)
modules = await ServerAPI.get_modules_list()
await PlatformAPI.restrict_member(session_info, user_id, duration=60)

# 仅等待数据库接受投递并返回任务 ID，不表示任务已送达或执行成功。
task_id = await PlatformAPI.post_message.submit(session_info, message, module_name)
await ServerAPI.receive_event.submit(event_info)

# 调用选项不占用业务函数的参数名称，也不会改变其返回类型。
modules = await ServerAPI.get_modules_list.with_timeout(10)()
```

同一 service 下的多个 Peer 会竞争领取普通 RPC。需要保持业务键路由亲和性的调用使用 `ServiceRoute`
描述 service、角色与路由键。任务入队前，运行时会查询权威 Registry，并通过 Rendezvous Hash 从
`ready` 实例中稳定选择一个目标。仅当不存在匹配实例时，任务才退回 service 任播队列，以便由稍后
启动的消费者领取。

因此，即使本地 `Alive` 缓存尚未收到 `draining` 信号，也不会继续将新任务直接投递至正在关闭的实例。
路由查询耗时计入 RPC deadline。Client 发往尚未启动的 Server 的任务可以保留在 service 队列中；
Server 发往无在线 Client 的主动平台操作则会立即返回 unavailable，避免产生长期无人领取的平台任务。

入站 `SessionInfo` 额外记录 `owner_peer_id`。删除消息、释放上下文、添加反应等依赖平台 SDK 上下文的
操作会直接投递至最初接收消息的 Client 实例。Server 创建的主动会话不设置 owner，而是依据场景键在
对应 service 内执行稳定路由。

## 信号广播

广播信号不是由多个消费者竞争领取的单条共享队列记录。发送端首先通过 `PeerSelector` 获取发送时刻
所有符合条件的 `ready` 实例快照，随后为每个目标分别创建一条实例直投记录。所有投递共享同一个
`event_id`，但各自具有独立的任务 ID、领取者、终态与 ACK。因此，任一目标执行失败不会影响其他目标
接收或确认同一信号。

```python
from core.queue.peer import PeerSelector
from core.queue.rpc import signal


@signal("cache.invalidate", timeout=30)
async def invalidate_cache(version: int) -> None: ...


@invalidate_cache.bind(JobQueueServer)
async def invalidate_server_cache(version: int) -> None:
    ...


# 仅确认各目标的投递记录已经写入。
receipt = await invalidate_cache.emit(PeerSelector.role("server"), version=8)

# 等待各目标处理完成，并按 peer_id 汇总 ACK 或错误。
report = await invalidate_cache.gather(PeerSelector.service("Server"), version=8)
```

同一信号可以在单个进程内注册多个本地订阅者。底层接口亦可直接调用
`JobQueueBase.emit_signal()` 或 `JobQueueBase.gather_signal()`；业务代码原则上应优先声明强类型
`SignalMethod`。接收端可以通过 `current_request`，或原始 `on_signal` 接口提供的 `SignalContext`，
读取可信的 `source_peer_id`。

信号处理器必须具备幂等性。用于同步配置、模块状态或其他版本化数据的信号应携带 version 或 epoch，
并以持久化状态为最终依据，不得仅依赖信号维持一致性。

## 多实例支持范围与约束

JobQueue 层已经支持同一 service 下多个 Client 或 Server 的注册、发现、实例直投、稳定分流与广播快照。
当前守护进程和配置系统仍仅会启动每类进程的单个实例。在正式启用多个 Server 之前，还需完成以下工作：

- 为 Scheduler 及其他仅应执行一次的后台任务引入 Leader Election 或分布式去重机制；
- 将模块加载、卸载与热重载等集群控制操作调整为逐 Server 扇出，并通过共享 epoch 完成状态对账；
- 明确 Server 故障后，进程内等待会话与临时状态的迁移方案或失效策略；
- 在生产规模下使用 MySQL 等适合多进程并发竞争的数据库，避免 SQLite 高频轮询导致锁竞争；
- 为具有外部副作用的业务处理器设计幂等键，因为队列仅保证原子领取，不提供 exactly-once 语义。

在同类型 Client 并行运行时，JobQueue 可以将入站会话相关操作定向返回原实例，并在同一 service 内对
主动任务进行稳定分流。但是，如果多个实例连接同一个平台账号，则平台 SDK 入口处的重复消费、分片租约
或主备接管仍须由适配器层实现。JobQueue 仅负责分流已经进入系统的任务，不负责消除平台侧重复产生的事件。

信号广播仅面向发送时刻在线的实例，不提供历史事件重放。对于离线期间亦须补齐的状态，应将其持久化，
并由 Peer 在启动后依据 version 或 epoch 主动对账；信号仅用于缩短在线实例感知状态变化的延迟。

普通模块继续使用 `MessageSession` 提供的便利方法。原有成员管理接口的 `wait` 参数保持不变：内部根据
参数选择普通调用或 `.submit()`；`wait=True` 时，成功返回 `None`，失败则抛出异常，不再返回
`{"success": True}`。发送接口返回消息 ID 列表，空列表仍表示平台未完成投递。

`client_init()` 与 Server 的 `main()` 会显式设置进程的默认 Peer。导入共享契约不会隐式确定进程角色，
也不会同时导入 Server 处理器或平台 SDK。请求处理期间，运行时通过 `ContextVar` 确定当前 Peer；
嵌套反向调用继续使用同一结果接收器。测试代码可以通过 `method.using(TestPeer)` 显式指定 Peer。

## 扩展接口

普通平台操作应先在 `ContextManager` 中声明能力并由各适配器实现，随后在 `PlatformAPI` 中暴露：

```python
new_capability = context_method(ContextManager.new_capability)
```

接口签名直接取自 `ContextManager`，接收端会自动解析上下文并转发调用，无须另行编写 Server 调用封装、
参数字典或 Client 处理器。同步的上下文 hold/release 方法同样通过该机制提供，跨进程调用始终可以 await。

服务端操作应在 `ServerAPI` 中声明具有完整类型注解的方法，并在 `server.py` 中绑定具体实现：

```python
# contracts.py / ServerAPI
@staticmethod
@remote("server.example", timeout=30)
async def example(name: str, enabled: bool = True) -> list[str]: ...

# server.py
@ServerAPI.example.bind(JobQueueServer)
async def example(name: str, enabled: bool = True) -> list[str]:
    return [name] if enabled else []
```

业务实现接收类型化参数并直接返回业务值。如果参数名称、参数种类或默认值与契约声明不一致，处理器注册将在
启动阶段立即失败；重复注册同样会被拒绝。运行时会在发送前和接收后分别执行参数绑定与编解码校验。
业务参数不得使用 `*args`；需要动态扩展参数时，应使用具有类型注解的 `**kwargs`。

动态 Hook 的参数与返回值支持 JSON 标量、列表、字符串键字典，以及已明确登记的消息、会话、事件和能力对象。
字典将作为整体编码，以避免与内部类型标记发生冲突。未经登记的 Python 对象会被拒绝，不会通过 pickle、
动态导入或任意对象反射在进程之间传递。

## 错误、超时与关闭语义

- `RpcRemoteError` 保留远端异常类型；所有 RPC 异常均包含方法名称、目标与请求 ID。
- `RpcMethodNotFoundError`、`RpcUnavailableError`、`RpcTimeoutError`、`RpcCancelledError` 与
  `RpcProtocolError` 分别表示方法未注册、目标不可达、请求过期、远端任务取消及协议错误。
- `None`、`False`、空列表与空字典均属于合法的成功返回值，不参与错误状态判断。
- 查询与信号的默认超时时间为 30 秒，普通操作为 120 秒，消息处理、消息发送及长操作最长为 7200 秒。
  每个请求具有独立的 deadline，不继承已经过期的父请求期限，以确保 `finally` 中的资源释放操作仍可执行。
- 调用方取消等待仅影响本地等待状态，不保证撤销远端副作用；远端处理仍受该请求自身 deadline 的约束。
- 原子领取可以避免同一投递被多个消费者重复执行，但不提供严格 FIFO 或 exactly-once 保证。
  如果外部副作用已经完成而响应丢失，则最终执行结果可能无法确定，因此不得自动重试发送、禁言等操作。
- 队列轮询与处理器并发运行；处理器等待反向调用时，不会阻塞结果接收。
- 进入维护状态时，实例停止领取新请求，但继续接收在途结果；待处理器全部结束后，方可独占数据库连接。
- 关闭过程中，结果接收器会持续运行，直至会话与后台任务清理完成，随后才停止轮询并关闭数据库连接。
- 实例正常退出或租约到期时，发往该实例的未完成直投任务会被标记为 unavailable。以 service 为目标的
  任播任务不会因单个实例退出而被删除，仍可由同组其他实例领取。
- 消息入口必须等待 Server 完成处理后再释放 Client 侧的 SDK 上下文，不得改为 `.submit()`。

## 协议升级与验证

协议 v2 属于破坏性替换。数据库 v5 同时增加信号关联与实例领取字段，并将旧字段 `target_client`
迁移为角色无关的 `target_peer`。新旧协议请求不得混合处理；升级时必须停止全部 Bot 与 Server 进程，
并在数据库迁移完成后统一启动。未知协议或旧协议请求会明确失败，不会被解释为新版本业务参数。

当前队列不承诺在机器人整体重启期间保留活动请求。单个 Server 退出时不得清空全局队列表，以免影响
同一 service 下其他实例正在处理或等待领取的任务。

自研测试框架的相关验证入口如下。执行时必须设置 `CI=1` 与 `PYTHONIOENCODING=UTF-8`：

- `tests/unit/test_rpc_contracts.py`：验证调用签名、默认值、业务对象 JSON 往返及平台接口自动绑定；
- `tests/unit/test_rpc_transport.py`：验证真实数据库往返、异常传播、取消、超时清理、维护与关闭流程；
- `tests/unit/test_rpc_process.py`：通过两个独立 Python 进程与临时 SQLite 验证并发反向调用；
- `tests/unit/test_queue_lifecycle.py`：验证原子领取、终态保留及活动任务清理；
- `tests/unit/test_peer_signals.py`：验证实例发现、同 service 任播、逐实例扇出、ACK 与租约到期；
- 会话、事件、平台关闭、主动推送、数据库维护与验证码测试用于覆盖上层迁移行为。

例如：

```bash
CI=1 PYTHONIOENCODING=UTF-8 uv run --no-sync python tests/run_one.py tests/unit/test_rpc_process.py
```
