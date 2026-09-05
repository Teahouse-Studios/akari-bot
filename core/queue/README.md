# JobQueue RPC

Bot 与 Server 进程使用同一套双向 RPC 运行时。业务代码调用共享的类型化接口，
不再分别维护 `add_job(action, args)` 和 `@action(tsk, args)`。

## 结构

| 文件 | 职责 |
| --- | --- |
| `contracts.py` | 稳定的方法名、签名、路由和默认超时 |
| `rpc.py` | 保留 Python 签名的代理、参数绑定、自动 handler 注册 |
| `codec.py` | 按类型编解码，复用消息与会话 converter |
| `base.py` | 每个 peer 的调用、结果关联、并发分发与生命周期 |
| `transport.py` | `RpcTransport` 协议及数据库实现；只有这里接触队列表 |
| `errors.py` | 可跨进程识别的异常类别 |
| `client.py` | 平台上下文解析、自动绑定及推送/私信等特殊行为 |
| `server.py` | 消息解析、事件、模块查询、钩子等服务端实现 |
| `reporting.py` | 保留配置中的错误报告，通过提交操作避免等待自身 |

数据库仍使用现有 `JobQueuesTable`，无表结构迁移。更换传输只需实现
`send / receive / responses / finish`，无需重写业务契约与 handler。

## 调用

```python
from core.queue.contracts import PlatformAPI, ServerAPI

# 等待执行结束；返回签名声明的值，失败抛 RpcError 子类。
message_ids = await PlatformAPI.send_message(session_info, message, quote=False)
modules = await ServerAPI.get_modules_list()
await PlatformAPI.restrict_member(session_info, user_id, duration=60)

# 只等待数据库接受，返回任务 ID；不代表已经送达或执行成功。
task_id = await PlatformAPI.post_message.submit(session_info, message, module_name)
await ServerAPI.receive_event.submit(event_info)

# 调用选项不占用业务函数的参数名，也不改变其返回类型。
modules = await ServerAPI.get_modules_list.with_timeout(10)()
```

普通模块继续使用 `MessageSession` 的便利方法。其原有成员管理 `wait` 参数保留，
内部选择普通调用或 `.submit()`；`wait=True` 成功返回 `None`，失败抛异常，
不再返回 `{"success": True}`。发送方法返回消息 ID 列表，空列表仍表示平台未送达。

`client_init()` 和 server 的 `main()` 显式设置默认 peer。导入契约不隐式选定进程角色，
也不会导入 server handler 或平台 SDK。处理请求期间通过 `ContextVar` 选择当前 peer，
反向调用使用同一个正在运行的结果接收器。测试可用 `method.using(TestPeer)` 指定 peer。

## 新增接口

普通平台操作在 `ContextManager` 定义能力并由适配器实现，随后在 `PlatformAPI` 暴露：

```python
new_capability = context_method(ContextManager.new_capability)
```

签名直接取自 `ContextManager`，接收端自动选择上下文并转发。
不需要新增 server 调用封装、参数字典或 client handler。
同步的上下文 hold/release 方法也由这一机制支持，跨进程调用始终可 await。

服务端操作在 `ServerAPI` 中声明带注解的方法，在 `server.py` 中绑定实际实现：

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

业务实现接收类型化参数，直接返回业务值。参数名、位置/关键字种类和默认值不匹配时，
启动注册立即失败；重复注册也失败。发送前及接收后都进行参数绑定和编解码。
业务参数不得使用 `*args`，动态扩展参数使用带注解的 `**kwargs`。

动态 hook 参数和返回值支持 JSON 标量、列表、字符串键字典，以及明确登记的消息、
会话、事件和能力对象。字典整体编码，避免与类型标记碰撞；未知 Python 对象被拒绝，
不会通过 pickle、动态导入或任意对象反射跨进程传递。

## 错误、超时与关闭

- `RpcRemoteError` 保留远端异常类型，所有 RPC 错误具有方法、目标和请求 ID 上下文。
- `RpcMethodNotFoundError`、`RpcUnavailableError`、`RpcTimeoutError`、
  `RpcCancelledError`、`RpcProtocolError` 分别表示未注册、不可达、过期、远端取消和协议错误。
- `None`、`False`、空列表、空字典都是合法成功值，不参与错误判断。
- 查询/保活默认 30 秒，普通操作 120 秒，消息处理/发送和长操作最多 7200 秒。
  每个请求有独立 deadline，不继承已经过期的父请求期限，允许 finally 中完成资源释放。
- 调用方取消只停止本地等待，不保证撤销远端副作用；远端仍受自身 deadline 约束。
- 原子领取避免同一任务被两个消费者执行，但没有自动重试、严格 FIFO 或恰好一次保证。
  副作用已完成但回包丢失时，结果可能不确定。不要自动重试发送、禁言等操作。
- 轮询与 handler 并发运行，handler 等待反向调用不会阻塞回包接收。
- 维护时停止领取新请求，继续接收在途结果，排空 handler 后独占数据库访问。
- 关闭时保留结果接收直到会话和后台任务清理完成，再停止轮询并关闭数据库。
- 消息入口仍等待 server 完成后才释放客户端 SDK 上下文，不能改成 `.submit()`。

## 升级与验证

这是内部协议替换，旧版本与新版本的请求不能混用。升级须停止全部 bot/server 进程后
一起启动；未知或旧协议请求显式失败，不会把旧参数误当作新业务参数执行。
当前队列仍不承诺跨机器人重启保存活动请求，server 关闭沿用现有清表流程。

自研框架验证入口（设置 `CI=1` 和 `PYTHONIOENCODING=UTF-8`）：

- `tests/unit/test_rpc_contracts.py`：签名、默认值、业务对象 JSON 往返及自动平台绑定。
- `tests/unit/test_rpc_transport.py`：真实数据库往返、异常、取消、超时清理、维护和关闭。
- `tests/unit/test_rpc_process.py`：两个独立 Python 进程和临时 SQLite，验证并发反向调用。
- `tests/unit/test_queue_lifecycle.py`：原子领取、终态保留及活跃任务清理。
- 会话、事件、平台关闭、主动推送、数据库维护和验证码测试覆盖上层迁移。

例如：`uv run --no-sync python tests/run_one.py tests/unit/test_rpc_process.py`。
