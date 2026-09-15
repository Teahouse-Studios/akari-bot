"""Parser / 出站生命周期入口点。

入口用显式常量，与旧式具名 hook（``.hook("name")``）正交：
具名 hook 走 ``Bot.Hook.trigger`` 的请求/返回语义；
入口订阅走 ``ParserHookExecutor``，按阶段分发并支持类型化结果。
"""

from enum import StrEnum


class HookPoint(StrEnum):
    """parser 与出站兼容阶段入口。"""

    # 入站检查通过后、等待任务投递前；补充临时元数据（不改身份/权限/等待键）
    SESSION_READY = "session.ready"
    # 冷却检查之后、读取模块及模块权限处理之前；ToS 临封检查
    COMMAND_PREPARE = "parser.command.prepare"
    # 模块权限处理后、模板解析前；ToS 令牌桶计数
    COMMAND_BEFORE_PARSE = "parser.command.before_parse"
    # 命令未匹配模块或模板时；纠错建议
    COMMAND_UNMATCHED = "parser.command.unmatched"
    # 正则匹配、去重之后；regex 侧 ToS 临封
    REGEX_PREPARE = "parser.regex.prepare"
    # regex 场景冷却之后、获取执行锁之前；regex 侧 ToS 计数
    REGEX_BEFORE_EXECUTE = "parser.regex.before_execute"
    # 命令/正则真实调用结束（旧 SessionFinished 分支）；统计观察
    EXECUTION_FINISHED = "parser.execution.finished"
    # 命令/正则抛出可分类异常时；ToS 业务拒绝等
    EXECUTION_ERROR = "parser.execution.error"
    # parser 主流程 finally 清理之后；消息级计数
    FINISHED = "parser.finished"
    # 公共出站协调层：安全检查之后、发往平台之前；可改写 chain
    OUTGOING_BEFORE_SEND = "outgoing.before_send"
    # 平台实际返回后观察
    OUTGOING_SENT = "outgoing.sent"
    # 平台发送失败后观察
    OUTGOING_FAILED = "outgoing.failed"


# 允许构建 SessionDraft 并在成功后提交的入口
SESSION_DRAFT_POINTS: frozenset[HookPoint] = frozenset(
    {
        HookPoint.SESSION_READY,
        HookPoint.COMMAND_PREPARE,
        HookPoint.COMMAND_BEFORE_PARSE,
        HookPoint.COMMAND_UNMATCHED,
    }
)

# 分发时按此顺序校验，未知入口拒绝注册
ALL_HOOK_POINTS: tuple[HookPoint, ...] = (
    HookPoint.SESSION_READY,
    HookPoint.COMMAND_PREPARE,
    HookPoint.COMMAND_BEFORE_PARSE,
    HookPoint.COMMAND_UNMATCHED,
    HookPoint.REGEX_PREPARE,
    HookPoint.REGEX_BEFORE_EXECUTE,
    HookPoint.EXECUTION_FINISHED,
    HookPoint.EXECUTION_ERROR,
    HookPoint.FINISHED,
    HookPoint.OUTGOING_BEFORE_SEND,
    HookPoint.OUTGOING_SENT,
    HookPoint.OUTGOING_FAILED,
)


__all__ = ["HookPoint", "ALL_HOOK_POINTS", "SESSION_DRAFT_POINTS"]
