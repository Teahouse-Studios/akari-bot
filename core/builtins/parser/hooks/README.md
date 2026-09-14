# Parser 入口 Hook API

模块通过 `@module.hook(point=...)` 订阅 parser 阶段，与旧式具名 hook（`.hook("name")`）正交。

## 快速开始

```python
from core.builtins.parser.hooks import Continue, HookPoint, Stop, StopScope
from core.component import module

ext = module("example-ext", hidden=True)


@ext.hook(point=HookPoint.COMMAND_PREPARE, priority=10, name="policy")
async def _(ctx):
    # ctx.msg / ctx.session_info / ctx.data / ctx.module_name
    if should_block(ctx.msg):
        return Stop(message=None, scope=StopScope.MESSAGE)
    return Continue()
```

## 入口一览

| HookPoint | 时机 | 典型用途 |
| --- | --- | --- |
| `SESSION_READY` | 入站检查后、等待任务前 | 补充 tmp；可写 SessionDraft |
| `COMMAND_PREPARE` | 冷却后、模块权限前 | ToS 临封；可写 SessionDraft |
| `COMMAND_BEFORE_PARSE` | 权限后、模板解析前 | ToS 计数；可写 SessionDraft |
| `COMMAND_UNMATCHED` | 未找到模块/模板 | 纠错建议；可写 SessionDraft |
| `REGEX_PREPARE` | 正则匹配去重后 | regex 临封 |
| `REGEX_BEFORE_EXECUTE` | regex 冷却后、取锁前 | regex 计数 |
| `EXECUTION_FINISHED` | 旧 SessionFinished 分支 | 统计观察 |
| `EXECUTION_ERROR` | 可分类异常 | AbuseWarning 处理 |
| `FINISHED` | parser finally 清理后 | 消息级计数 |
| `OUTGOING_BEFORE_SEND` | 安全检查后、平台发送前 | 消息转换；可改 `ctx.outgoing.chain` |
| `OUTGOING_SENT` | 平台返回成功 | 观察 |
| `OUTGOING_FAILED` | 平台发送失败 | 观察 |

## 结果类型

- `Continue()`（或 `None`）：继续
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
async def _(ctx):
    ctx.draft.set_tmp("tag", "1")
    return Continue()
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
- 依赖对 SessionInfo 物理身份的写入（本期无草稿事务）

## 内置订阅方

- `modules/core/tos.py`：临封、令牌桶、上报；四个强制检查不限时且检查故障按消息级 `Stop` 处理，
  避免失败放行；具名能力 `tos.check_temp_ban` / `tos.remove_temp_ban` / `tos.report`
- `modules/core/telemetry.py`：AnalyticsData 与 Info 计数
- `modules/core/typo.py`：纠错 RecoveryProposal
