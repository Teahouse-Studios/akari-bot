"""Parser / 出站生命周期入口点。"""

from enum import StrEnum


class HookPoint(StrEnum):
    """parser 与出站生命周期入口。"""

    # 会话信息刷新后、等待任务投递前；过滤消息或补充临时元数据
    SESSION_READY = "session.ready"
    # 会话入口策略完成后、投递等待任务前；决定是否交给等待任务消费
    SESSION_BEFORE_WAIT = "session.before_wait"
    # 消息文本规范化后、前缀判断前；允许重写触发文本
    MESSAGE_NORMALIZED = "parser.message.normalized"
    # 命令候选选定后、模块处理前；冷却、临封和模块策略
    COMMAND_PREPARE = "parser.command.prepare"
    # 模块权限处理后、模板解析前；ToS 令牌桶计数
    COMMAND_BEFORE_PARSE = "parser.command.before_parse"
    # 模板解析后、命令函数调用前；命令级权限与平台策略
    COMMAND_BEFORE_EXECUTE = "parser.command.before_execute"
    # 命令候选通过前缀/别名解析后、通道认领前；路由策略
    COMMAND_ROUTE = "parser.command.route"
    # 命令未匹配模块或模板时；纠错建议
    COMMAND_UNMATCHED = "parser.command.unmatched"
    # 消息完成基础规范化后、开始遍历正则候选前；正则路由策略
    REGEX_ROUTE = "parser.regex.route"
    # 每个正则模块候选匹配前；模块级路由策略
    REGEX_CANDIDATE = "parser.regex.candidate"
    # 命令或正则候选通过策略后、通道认领前；通道让位策略
    CHANNEL_CLAIM = "parser.channel.claim"
    # 正则匹配并完成候选去重后；regex 侧策略
    REGEX_PREPARE = "parser.regex.prepare"
    # regex 场景冷却之后、获取执行锁之前；regex 侧 ToS 计数
    REGEX_BEFORE_EXECUTE = "parser.regex.before_execute"
    # 命令/正则真实调用结束；统计观察
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
    HookPoint.SESSION_BEFORE_WAIT,
    HookPoint.MESSAGE_NORMALIZED,
    HookPoint.COMMAND_PREPARE,
    HookPoint.COMMAND_BEFORE_PARSE,
    HookPoint.COMMAND_BEFORE_EXECUTE,
    HookPoint.COMMAND_ROUTE,
    HookPoint.COMMAND_UNMATCHED,
    HookPoint.REGEX_ROUTE,
    HookPoint.REGEX_CANDIDATE,
    HookPoint.CHANNEL_CLAIM,
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
