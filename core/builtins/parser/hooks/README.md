# Parser 入口 Hook API

模块通过 `@module.hook(point=...)` 订阅 parser 阶段；具名能力（`.hook("name")`）也由同一套订阅执行基础负责。

## 具名 Module Hook

具名 hook 通过 `Bot.Hook.trigger("module.name", session_info=..., args=...)` 调用。
它与 parser hook 共享模块启用状态、平台过滤、runtime generation、超时和取消收尾：

- `module.name`：执行指定能力，返回最后一个成功回调的返回值；异常直接传播给调用方。
- `module`：按优先级执行该模块全部未指定 `point` 的具名 hook；单个回调失败会记录并继续，返回值不向广播调用方汇总。
- 具名 hook 默认执行预算为 5 秒，可在 `@module.hook(..., timeout=...)` 覆盖；传 `timeout<=0` 表示不限时。
- 具名 hook 的 `available_for` / `exclude_from` 会基于传入的 `session_info` 检查；没有会话时只执行全平台订阅。

测试和计划任务 mock 也调用同一分发入口，不应直接取 `ModulesManager.modules_hooks` 调函数。

## 快速开始

```python
from typing import TYPE_CHECKING

from core.builtins.parser.hooks import HookPoint
from core.component import module

if TYPE_CHECKING:
    from core.builtins.bot import Bot

ext = module("example-ext", hidden=True)


@ext.hook(point=HookPoint.COMMAND_PREPARE, priority=10, name="policy")
async def _(ctx: "Bot.ParserHookContext"):
    # ctx.msg / ctx.session_info / ctx.data / ctx.module_name
    if should_block(ctx.msg):
        return ctx.Stop(scope=ctx.StopScope.MESSAGE)
    return ctx.Continue()
```

## 入口一览

| HookPoint | 时机 | 典型用途 |
| --- | --- | --- |
| `SESSION_READY` | 会话刷新后、等待任务前 | 入站过滤、补充 tmp；可写 SessionDraft |
| `SESSION_BEFORE_WAIT` | 入站策略后、等待任务投递前 | 调整等待任务路由 |
| `MESSAGE_NORMALIZED` | 消息文本规范化后、前缀判断前 | 自定义别名等触发文本改写 |
| `COMMAND_PREPARE` | 命令候选后、模块权限前 | 冷却、ToS 临封；可写 SessionDraft |
| `COMMAND_BEFORE_PARSE` | 模块策略后、模板解析前 | ToS 计数；可写 SessionDraft |
| `COMMAND_BEFORE_EXECUTE` | 模板解析后、命令函数调用前 | 命令权限与平台策略 |
| `COMMAND_ROUTE` | 命令解析后、通道认领前 | 命令路由与迁移策略 |
| `COMMAND_UNMATCHED` | 未找到模块/模板 | 纠错建议；可写 SessionDraft |
| `REGEX_ROUTE` | 消息规范化后、正则候选遍历前 | 正则禁用前缀、静音与运行中提醒 |
| `REGEX_CANDIDATE` | 每个正则模块匹配前 | 模块级正则路由 |
| `CHANNEL_CLAIM` | 候选策略通过后、通道认领前 | 通道让位策略 |
| `REGEX_PREPARE` | 正则匹配并完成循环去重后 | regex 临封与权限 |
| `REGEX_BEFORE_EXECUTE` | regex 冷却后、取锁前 | regex 计数 |
| `EXECUTION_FINISHED` | 命令/正则函数执行结束 | 统计观察 |
| `EXECUTION_ERROR` | 可分类异常 | AbuseWarning 处理 |
| `FINISHED` | parser finally 清理后 | 消息级计数 |
| `OUTGOING_BEFORE_SEND` | 安全检查后、平台发送前 | 消息转换、静音场景拦截主动发言；可改 `ctx.outgoing.chain` |
| `OUTGOING_SENT` | 平台返回成功 | 观察 |
| `OUTGOING_FAILED` | 平台发送失败 | 观察 |

## 结果类型

- `Continue()`（或 `None`）：继续
- `RewriteTrigger(trigger_msg)`：提交新的触发文本并继续同入口的后续 hook
- `Stop(message=..., scope=CANDIDATE|MESSAGE)`：业务拒绝；出站入口表示取消发送
- `RecoveryProposal(trigger_msg, command_first_word, display)`：恢复建议
- `Handled()`：错误入口已处理（观察入口禁止）

非法返回值按失败隔离，不会短路后续 hook。

## SessionDraft

`SESSION_DRAFT_POINTS` 上每个 hook 获得独立草稿；成功才 `commit()`，失败/超时 `revoke()`。

可写字段：`tmp` / `prefixes` / `messages` / `bot_name` / `muted` / `locale_lang`。

`locale_lang` 写入时必须是非空、非空白字符串；`None`、空串等无效值会抛出 `SessionDraftError`，
不会标记字段变更。未修改语言且原会话没有语言时，读取仍可返回 `None`。
`ctx.session_info` 的容器返回独立副本，Union ORM 及关联对象只允许读取属性，禁止调用其方法。

```python
@ext.hook(point=HookPoint.COMMAND_PREPARE)
async def _(ctx: "Bot.ParserHookContext"):
    ctx.draft.set_tmp("tag", "1")
    return ctx.Continue()
```

身份、权限、ORM、执行锁不在草稿内。

## 出站

`before_send` 通过 `ctx.outgoing` 改写 `chain` / `quote`；递归 send 跳过嵌套改写。`sent`/`failed` 只观察，不改写原结果。

结果观察中的 `chain` 是改写后完成过滤、平台转换与安全检查的实际发送内容，`message_ids` 来自平台返回值。构建快照或运行观察者失败只记日志，不影响已发送消息的返回结果，也不遮蔽原始发送异常；外部取消与进程退出仍传播。

`send_direct_message()` 的 `submit` 成功仅表示队列接受投递，因此不发布 `OUTGOING_SENT`；投递本身失败时发布 `OUTGOING_FAILED`。

## 执行契约

- 串行；优先级升序 → 模块名 → 订阅 ID
- 单 hook 异常 / 超时 / SessionFinished 等协议异常：丢弃并继续
- 外部 `CancelledError` / `SystemExit` / `KeyboardInterrupt` 传播
- 模块 `_db_load` / `load` 为假时不执行
- 订阅绑定构建时的 module generation；热重载后旧代际回调跳过
- `timeout` 默认 5s，可按订阅覆盖；`<=0` 不限时
- `available_for` / `exclude_from` 语义同 command
- 无订阅时 parser 不扫描模块

## 故障边界

hook 不得：

- 用 `msg.finish()` / 抛 `SessionFinished` 表达业务拒绝（请用 `Stop`）
- 在观察入口吞掉原异常或改写执行结果
- 依赖对 SessionInfo 身份字段的写入（可写字段必须经 `SessionDraft` 提交）

## 内置订阅方

- `modules/core/hooks/policies.py`：入站、冷却、权限、正则路由、出站静音和默认命令反馈
- `modules/core/hooks/errors.py`：异常反馈与错误详情格式化
- `modules/core/hooks/retired.py`：退役客户端路由和通道让位
- `modules/core/admin_tools/alias.py`：自定义别名改写
- `modules/core/hooks/routing.py`：同通道消息认领
- `modules/core/hooks/tos.py`：临封、令牌桶、上报；四个强制检查不限时且检查故障按消息级 `Stop` 处理，
  避免失败放行；具名能力 `tos.check_temp_ban` / `tos.remove_temp_ban` / `tos.report`
- `modules/core/hooks/telemetry.py`：AnalyticsData 与 Info 计数
- `modules/core/hooks/typo.py`：纠错 RecoveryProposal
