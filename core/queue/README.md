# JobQueue Peer RPC 与信号总线

Bot 与 Server 进程共用一套双向 RPC 与信号运行时。运行时通过配置装配一套完整的 JobQueue 后端；
该后端同时提供 Peer Registry（进程实例注册表）和消息传输能力，二者不得跨后端组合。
当前提供数据库与 WebSocket 两种互斥后端。进程内的 `Alive` 仅作为同步路由缓存，并通过权威 Registry
定期对账；任何未经当前后端确认的缓存记录均不得视为在线实例。

## 组件与职责

| 文件 | 职责 |
| --- | --- |
| `contracts.py` | 声明稳定的方法名称、调用签名、路由规则与默认超时时间 |
| `rpc.py` | 提供保留 Python 签名的调用代理、参数绑定及处理器自动注册机制 |
| `codec.py` | 按声明类型执行编解码，并复用消息与会话对象的转换器 |
| `base.py` | 管理 Peer 调用、结果关联、并发分发、信号扇出及生命周期 |
| `backend.py` | 定义完整后端协议，并依据配置装配相互一致的 Registry 与 Transport |
| `transport.py` | 定义介质无关的消息信封、批量投递结果及 `MessageTransport` 协议 |
| `peer.py` | 定义进程身份、目标选择、Registry 协议及信号投递结果 |
| `database.py` | 实现数据库 Registry、任务传输、原子领取及实例失效后的任务终结 |
| `websocket.py` | 实现基于 `httpx-ws` 的客户端、ASGI Hub、连接鉴权、实时路由及背压控制 |
| `memory.py` | 提供不依赖 ORM 的后端契约测试基座，不作为生产配置选项 |
| `errors.py` | 定义可跨进程识别的异常类型 |
| `client.py` | 解析平台上下文，自动绑定平台接口，并处理推送、私信等特殊逻辑 |
| `server.py` | 实现消息解析、事件分发、模块查询与钩子调用等服务端接口 |
| `reporting.py` | 提交配置中指定的错误报告，并避免错误报告流程等待自身完成 |

数据库后端使用 `JobQueuePeersTable` 以 `peer_id` 为主键登记每个进程实例。`JobQueuesTable` 中的
`target_peer`、`source_peer_id`、`correlation_id`、`message_kind`、`expects_response` 与 `claimed_by`
分别记录投递目标、来源实例、关联标识、消息类别、是否需要回包及实际领取者。

新增后端必须同时实现 `JobQueueBackend`、`PeerRegistry` 与 `MessageTransport` 契约。Registry 负责注册、
续租或连接保活、权威实例发现及路由选择；Transport 负责请求、响应、批量投递和本地放弃状态的处理。
接收端通过 `respond(request, response)` 回包，原始请求提供无状态传输所需的返回路由上下文。
`abandon()` 仅表示调用方停止等待并要求后端尽力清理，不能解释为已经撤销远端执行。

## 配置与后端选择

JobQueue 配置独立存放于 `config/jobqueue.toml`。`[jobqueue].jobqueue_backend` 用于选择整套后端，
有效值为 `database` 和 `websocket`；`[jobqueue_secret]` 仅存放 WebSocket Hub 访问令牌等敏感配置。
所有参与同一逻辑集群的进程必须使用相同后端，运行期间不支持热切换。未知值会明确终止初始化，
WebSocket Hub 无法连接或鉴权失败时亦不会自动回退至数据库，以免同一集群同时形成两套互不一致的
通信通道。

新生成的配置默认选择 `websocket`，该后端亦是项目的推荐选项。已明确配置为 `database` 的部署不会被自动
改写或静默切换。当守护进程检测到 JobQueue 使用 `database` 且主数据库为 SQLite 时，会在数据库初始化前
输出一次非阻断警告，但仍严格按现有配置启动。

两种生产后端的主要差异如下：

| 比较项 | `database` | `websocket` |
| --- | --- | --- |
| 部署要求 | 复用共享数据库，无须另行部署 Hub | 需要一个独立 Hub，并维持各 Peer 的长连接 |
| 投递特性 | 轮询数据库；尚未过期的队列记录可供稍后启动的消费者领取 | 实时在线路由；不持久化离线任务或在途结果 |
| 资源与时延 | 轮询、写入及终态清理会增加数据库 CPU 与 I/O 负载，时延受轮询间隔影响 | 不产生数据库轮询负载，通常具有更低时延，但需承担连接、背压和 Hub 运维成本 |
| 适用范围 | 使用 MySQL 等可并发写入的共享数据库，或明确接受写锁竞争的 SQLite 低负载部署 | 默认与推荐选项；适用于 SQLite、高频 RPC、信号广播及同类多实例并行运行 |
| 故障边界 | 受共享数据库可用性与容量限制 | Hub 重启或连接中断会丢失内存中的拓扑及在途关联，远程部署还须配置令牌与 TLS |

数据库后端不提供 exactly-once、无限期持久化或副作用请求的安全自动重试。WebSocket 后端也不以实时性
换取此类保证；Hub 无法确定投递结果时会报告 unknown，而不会擅自重试。即使 JobQueue 选择 WebSocket，
业务模型和模块数据库仍可能要求初始化数据库连接，因此该选项不属于全局数据库开关。

### SQLite 写锁边界

当主数据库为 SQLite 时，`database` 后端与业务模型共用同一数据库文件。SQLite 即使在 WAL 模式下仍只允许
同一时刻存在一个写者；WAL 主要改善读写并行，不会把单写者模型变为多写者模型。JobQueue 的任务投递、原子
领取、Peer 心跳、结果回写及清理均会与业务写入竞争该写锁。因此，以下措施只能减少锁冲突，不能承诺
消除 `database is locked` 错误：

- 所有 SQLite 连接均先设置 30 秒 `busy_timeout`，再启用 WAL，使并发启动期间的 WAL 初始化也受等待策略保护；
- 任务领取始终使用带 `pending` 状态条件的原子更新，并将每轮候选记录限制为 100 条，避免积压时单轮无界
  扫描与连续写入；
- 终态结果在调用方读取后立即删除，免回包任务在完成时直接删除，并由定时清理回收调用方异常退出后残留的终态记录；
- Peer 失效时的状态切换与直投任务终结仍保留在同一事务中。该路径会延长少量写锁的持有时间，但不应为缩短锁时间而
  破坏 Peer 状态与投递结果的一致性。

需要降低 SQLite 锁竞争时，应优先将 JobQueue 切换为 `websocket`。该调整只移除 JobQueue 自身对 SQLite 的轮询与写入，
不会消除业务模型之间原有的 SQLite 写锁竞争。如果必须持续使用数据库后端并承载多进程高频写入，应使用 MySQL 等
适合并发写入的共享数据库。

`PeerSelector` 支持按实例、节点、角色、service 与 capability 的交集筛选目标，并可显式排除指定实例。
`InMemoryJobQueueBackend` 由同一测试集群中的多个 Peer 共享 `InMemoryBroker`，用于验证 Runtime 不再隐式
依赖数据库模型。该实现不提供跨进程通信、持久化或生产可靠性保证，配置工厂不会接受 `memory`。

## 实例身份、寻址与发现

每个进程具有两层身份：

- `JobQueueBase.name` 是在每次进程生命周期内生成的唯一 `peer_id`。以该标识投递的任务仅能由对应
  实例领取。PID 作为诊断信息随实例登记，但不参与寻址。
- `PeerIdentity.service` 是稳定的服务组标识，例如 `Server` 或 `QQ`。同一服务组中的实例共同监听
  该标识。数据库后端通过原子 `claim()`、WebSocket 后端通过 Hub 集中选择目标，确保每条普通 RPC 只会
  被分配给一个实例，从而实现任播（anycast）负载均衡。

`node_id` 是可配置的部署节点标签。正常启动时，`pre_init` 会在创建任何 Hub、Bot 或 Server 子进程之前
检查 `[jobqueue].jobqueue_node_id`；该值不存在、仍为占位符或仅包含空白字符时，系统生成一个 UUID，原子写回
配置文件后再继续启动。因此，共用同一配置目录的进程会取得相同且可跨重启保持稳定的 `node_id`，而每个进程
实例仍由独立的 `peer_id` 唯一标识。系统不会从计算机名、宿主机环境或其它设备信息中读取或推导该值。

若需要按物理节点或部署单元选择一组 Peer，可为相关进程共用配置，也可显式设置相同且不包含敏感信息的
`jobqueue_node_id`。调用 `configure_peer()` 时显式传入的 `node_id` 具有最高优先级。绕过正常守护进程直接
启动单个 Peer，且配置值仍为空时，运行时仍会为该进程生成临时 UUID 作为防御性回退，但不会将其视为常规
部署路径。配置值最长为 128 个字符，修改后须重启相关进程才会反映到 Peer Registry。

同一 service 表示一组能够相互替代并承接同类任务的实例。节点标签、PID、capabilities 与自定义 metadata
均独立登记，因此后续可以在不修改 RPC 业务载荷的前提下增加权重、分片或区域等路由约束。
无法相互替代的平台账号应使用不同的 service；如确需归入同一 service，则必须在启用多实例之前
补充能够区分账号或分片的路由条件。

`check_job_queue()` 启动时依次完成以下操作：以 `starting` 状态注册实例、启用实例寻址、切换为
`ready`、读取完整拓扑，并向现有在线实例广播 `peer.ready`。运行期间，每 15 秒续订一次租约，
每 10 秒依据当前后端的权威 Registry 执行一次完整拓扑对账。正常关闭时，实例先通过 `peer.draining`
停止接收新任务，
完成在途任务清理后再广播 `peer.stopped`；异常退出则在 45 秒租约到期后被识别。

保活信息不再定向发送至某个 Server，因此多个 Server 可以依据同一权威注册表获得一致的在线视图。
数据库热重载等维护操作会将实例状态切换为 `maintenance`，并广播 `peer.maintenance`，使该实例暂时退出
稳定路由。连接恢复后，实例重新注册为 `ready` 并广播 `peer.resumed`，从而避免在维护期间接收新消息。

所有生命周期信号均须由其载荷中对应的 `peer_id` 发出，并且仅在信号内容与 Registry 当前状态一致时
更新本地缓存。延迟到达的 `ready`、`resumed` 或 `stopped` 信号不得覆盖更新后的权威状态；同一进程内的
轮询器异常重启并以原 `peer_id` 重新取得有效租约时，则允许经 Registry 确认的新 `ready` 状态覆盖本地
`stopped` 缓存。

## WebSocket Hub 部署

WebSocket 后端由一个独立 Hub 和任意数量的 Peer 连接组成。Hub 不属于业务 Server，不执行模块逻辑，
其职责仅限于维护连接身份、权威 Peer 状态、任播选择、逐实例信号投递和在途响应关联。内置部署模式下，
机器人守护进程会先启动名为 `jobqueue-hub` 的独立子进程，确认监听端口就绪后再启动 Bot 与 Server；关闭时
则先停止 Bot 和 Server，最后停止 Hub，以便在退出阶段继续传递回包与生命周期信号。

```toml
[jobqueue]
jobqueue_backend = "websocket"
jobqueue_websocket_mode = "embedded"
jobqueue_websocket_url = "ws://127.0.0.1:8765/jobqueue"
jobqueue_websocket_queue_size = 1000
jobqueue_websocket_max_message_bytes = 1048576
jobqueue_websocket_command_timeout = 10

[jobqueue_secret]
jobqueue_websocket_token = ""
```

`jobqueue_websocket_mode` 明确 Hub 的部署模式：`embedded` 表示由机器人守护进程启动内置 Hub，
`external` 表示各 Peer 仅连接独立部署的外部 Hub。部署模式不得依据 URL 的主机地址推断，以免本机外部 Hub
被误判为内置 Hub。`jobqueue_websocket_url` 是 WebSocket 地址的唯一配置来源；在 `embedded` 模式下，
Hub 的监听主机、监听端口和协议路径均从该 URL 解析，各 Peer 亦连接同一地址；在 `external` 模式下，
该 URL 仅表示 Peer 的连接地址。

正常启动时，如果 `jobqueue_websocket_token` 不存在、仍为占位符或仅包含空白字符，`pre_init` 会生成一个
具有 256 位随机熵的 URL-safe 密钥并写回 `[jobqueue_secret]`，随后 Hub、Bot 与 Server 子进程只读同一值。
清空该字段会在下次启动时轮换密钥；轮换后，使用旧密钥的 Peer 将无法通过鉴权。自动生成适用于共用同一
配置目录的本机部署；使用外部 Hub 或多个独立配置目录时，必须将同一密钥安全地配置到全部参与节点。

内置 Hub 不负责 TLS 终止，因此 `embedded` 模式仅接受使用 `ws` 的回环地址。连接非回环外部 Hub 时必须
使用 `wss` 和共享访问令牌。生产环境宜通过反向代理终止 TLS，
并将 Hub 本身限制在受信网络内。单一 `embedded` 配置不表达“监听通配地址，但通过另一域名连接”的双地址
部署；多节点、反向代理或其它需要区分监听地址与连接地址的场景应使用 `external` 模式，由外部部署系统分别
管理 Hub 的监听端点与公开连接地址。

Hub 在握手阶段将连接绑定至唯一 `peer_id`，此后不信任请求载荷自行声明的 `source_peer_id`，而是统一以连接
身份覆盖该字段。重复连接同一 `peer_id`、身份越权修改、非目标 Peer 回包及畸形协议帧均会被拒绝。

使用外部 Hub 时，应将 `jobqueue_websocket_mode` 设置为 `external`，并确保所有 Peer 配置相同的连接 URL
与访问令牌。项目所附 Hub 可通过 `uv run python -m core.queue.websocket` 独立启动；此时应在 Hub 主机上
提供适用于其监听端点的独立配置。该进程不负责自动发现其它 Hub，也不提供多 Hub 状态复制；同一逻辑集群
在任一时刻必须连接至同一个权威 Hub。

WebSocket 后端属于实时、非持久化传输。Hub 对每个 Peer 设置有界发送队列，并限制单帧大小；目标队列已满时，
新投递会被明确拒绝。控制命令在发送后超时则按 unknown 处理，不得据此自动重试有外部副作用的请求。目标
断线、主动注销或租约过期时，Hub 会立即将其未完成直投请求终结为 unavailable；来源断线时，Hub 删除其
响应关联状态。超过请求 deadline 的关联状态会被及时释放，并向仍在线的来源返回 timeout；此清理不会撤销
已经开始的远端副作用。Hub 自身重启会丢失全部 Peer 与在途请求，所有 Peer 必须重新连接并注册。

## RPC 调用

```python
from core.queue.contracts import PlatformAPI, ServerAPI

# 等待远端执行完成。成功时返回签名声明的值，失败时抛出 RpcError 子类。
message_ids = await PlatformAPI.send_message(session_info, message, quote=False)
modules = await ServerAPI.get_modules_list()
await PlatformAPI.restrict_member(session_info, user_id, duration=60)

# 仅等待当前后端接受投递并返回任务 ID，不表示任务已送达或执行成功。
task_id = await PlatformAPI.post_message.submit(session_info, message, module_name)
await ServerAPI.receive_event.submit(event_info)

# 调用选项不占用业务函数的参数名称，也不会改变其返回类型。
modules = await ServerAPI.get_modules_list.with_timeout(10)()
```

同一 service 下的多个 Peer 会竞争领取普通 RPC。需要保持业务键路由亲和性的调用使用 `ServiceRoute`
描述 service、角色与路由键。任务投递前，运行时会查询权威 Registry，并通过 Rendezvous Hash 从
`ready` 实例中稳定选择一个目标。数据库后端在不存在匹配实例时可以将任务保留在 service 任播队列，
以便由稍后启动的消费者领取；WebSocket 后端不保留离线任务，会明确返回 unavailable。

因此，即使本地 `Alive` 缓存尚未收到 `draining` 信号，也不会继续将新任务直接投递至正在关闭的实例。
路由查询耗时计入 RPC deadline。数据库后端允许 Client 发往尚未启动的 Server 的任务暂时保留在 service
队列中；不具备离线持久化能力的后端可以立即返回 unavailable。Server 发往无在线 Client 的主动平台操作
仍会立即失败，避免产生长期无人领取的平台任务。

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


# 仅确认当前后端已经明确接受的目标投递。
receipt = await invalidate_cache.emit(PeerSelector.role("server"), version=8)

# 等待各目标处理完成，并按 peer_id 汇总 ACK 或错误。
report = await invalidate_cache.gather(PeerSelector.service("Server"), version=8)
```

`.emit()` 投递不要求回包；数据库后端会在各目标处理完成后删除相应队列行。`.gather()` 要求逐实例 ACK，
数据库终态结果由发起方读取后立即删除。批量发送允许后端逐项报告 accepted、rejected 与 unknown；
`SignalReceipt` 仅将明确接受的投递列入 `deliveries`，拒绝原因和接受状态未知的 Peer 分别列入 `errors`
与 `unknown`。其中的任务 ID 仅用于关联本次投递，不表示后端会将其持久保留。

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
- timeout 与 deadline 必须为正的有限数值或有限时间戳；布尔值虽然在 Python 中属于整数子类，仍将被明确
  拒绝。响应错误码等协议字段亦须符合约定类型，畸形数据统一转换为 `RpcProtocolError`，不得泄漏底层
  类型异常。
- 调用方取消等待时会调用后端的 `abandon()` 尽力清理本地及尚可撤销的传输状态，但不保证撤销已经开始的
  远端副作用；远端处理仍受该请求自身 deadline 的约束，其最终完成状态可能无法再由调用方取得。
- 投递操作可能在后端已经接受消息后才报告取消或连接异常。等待型调用在此情况下按“投递结果未知”处理，
  并以预先生成的任务 ID 尝试清理；该操作不改变远端副作用可能已经发生的事实。
- 数据库后端的原子领取和 WebSocket Hub 的集中目标选择可以避免同一投递同时分配给多个消费者，但均不提供
  严格 FIFO 或 exactly-once 保证。
  如果外部副作用已经完成而响应丢失，则最终执行结果可能无法确定，因此不得自动重试发送、禁言等操作。
- `.submit()` 与 `.emit()` 不等待远端结果。数据库后端在处理器进入终态后直接删除任务行；等待型 RPC 与
  `.gather()` 在发起方读取终态结果后立即删除任务行。终态记录不是审计日志，不应依赖其持久存在。
- 数据库后端已经将终态结果读入内存后，若删除操作发生瞬时故障，应优先交付有效结果并记录清理异常，避免
  结果泵退出或将成功结果降级为 unavailable；未删除的终态行仍由定时任务兜底回收。
- 调用方异常退出等情况可能遗留未消费的终态结果；定时清理仅作为兜底，并通过 `(status, timestamp)`
  索引限制数据库扫描成本。WebSocket Hub 不持久化终态结果，来源连接关闭后会直接释放相关状态。
- 队列轮询与处理器并发运行；处理器等待反向调用时，不会阻塞结果接收。
- 进入维护状态时，实例停止领取新请求，但继续接收在途结果；待处理器全部结束后，方可进入需要独占资源的
  维护操作。数据库热重载在此阶段独占数据库连接。
- 同一任务可以重入维护窗口；不同任务发起的维护窗口按实例串行执行，以避免不可重入锁导致死锁，或后续
  维护在 Registry 已恢复 `ready` 状态后继续运行。
- 关闭过程中，结果接收器会持续运行，直至会话与后台任务清理完成，随后才停止接收并关闭 JobQueue 后端。
- 队列轮询器异常退出时，实例会主动撤销 Registry 注册并释放本地等待方，不继续以可路由但无法收发任务的
  状态存活。Client 监督器可在状态清理完成后重新启动轮询器；Server 则将异常上抛至进程监督逻辑。
- 实例正常退出或租约到期时，发往该实例的未完成直投任务会被标记为 unavailable。数据库中尚未领取的
  service 任播任务不会因单个实例退出而被删除，仍可由同组其他实例领取；实例状态更新与其直投任务终结
  位于同一数据库事务内。WebSocket 请求一经 Hub 选择目标即成为实例直投，目标断线后不会重新分配，以免
  非幂等处理器被重复执行。
- 消息入口必须等待 Server 完成处理后再释放 Client 侧的 SDK 上下文，不得改为 `.submit()`。

## 协议升级与验证

协议 v2 属于破坏性替换。数据库从 v4 升级至 v5 时，将直接删除既有 `job_queues` 表，并依据当前
ORM 模型重新创建该表；旧表中的待领取、执行中及已完成任务均不予保留。包括 `job_queue_peers` 在内
的新增表亦由当前模型统一创建。新旧协议请求不得混合处理；升级前必须停止全部 Bot 与 Server 进程，
并在数据库迁移完成后统一启动。未知协议或旧协议请求会明确失败，不会被解释为新版本业务参数。

当前队列不承诺在机器人整体重启期间保留活动请求。单个 Server 退出时不得清空全局队列表，以免影响
同一 service 下其他实例正在处理或等待领取的任务。

自研测试框架的相关验证入口如下。执行时必须设置 `CI=1` 与 `PYTHONIOENCODING=UTF-8`：

- `tests/unit/test_rpc_contracts.py`：验证调用签名、默认值、业务对象 JSON 往返及平台接口自动绑定；
- `tests/unit/test_jobqueue_backend.py`：验证后端整套装配、配置选择、生命周期及禁止静默回退；
- `tests/unit/test_jobqueue_memory_backend.py`：在不访问 JobQueue ORM 表的后端上验证 RPC、信号和失效传播；
- `tests/unit/test_jobqueue_websocket_backend.py`：通过真实回环连接和独立进程验证 WebSocket 鉴权、发现、
  任播、逐实例信号、双向 RPC、反向调用及断线传播；
- `tests/unit/test_jobqueue_daemon.py`：验证内置 Hub 的启动屏障、外部 Hub 与数据库模式、启动失败回滚及
  Bot、Server、Hub 的有序关闭；
- `tests/unit/test_rpc_transport.py`：验证真实数据库往返、异常传播、取消、超时清理、维护与关闭流程；
- `tests/unit/test_rpc_process.py`：通过两个独立 Python 进程与临时 SQLite 验证并发反向调用；
- `tests/unit/test_queue_lifecycle.py`：验证原子领取、结果消费后删除、免回包任务删除及活动任务清理；
- `tests/unit/test_peer_signals.py`：验证实例发现、同 service 任播、逐实例扇出、ACK 与租约到期；
- 会话、事件、平台关闭、主动推送、数据库维护与验证码测试用于覆盖上层迁移行为。

例如：

```bash
CI=1 PYTHONIOENCODING=UTF-8 uv run --no-sync python tests/run_one.py tests/unit/test_rpc_process.py
```
