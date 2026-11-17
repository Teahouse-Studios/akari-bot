"""Parser 入口 hook 的类型化结果。"""

from __future__ import annotations

from enum import StrEnum

from attrs import define, field

from core.builtins.message.chain import MessageChain


class HookResult:
    """入口 hook 返回值的基类。"""


@define
class Continue(HookResult):
    """继续后续 hook 与默认流程。"""

    data: dict = field(factory=dict)


@define
class RewriteTrigger(HookResult):
    """提交新的触发文本并继续当前入口的后续 hook。"""

    trigger_msg: str


class StopScope(StrEnum):
    """``Stop`` 的作用域。"""

    CANDIDATE = "candidate"
    MESSAGE = "message"


@define
class Stop(HookResult):
    """业务拒绝：停止当前候选组件或整条消息。

    :param message: 可选的用户可见提示；由 parser 统一发送。
    :param scope: ``candidate`` 停止当前命令/正则候选；``message`` 停止整条消息处理。
    :param data: 供后续策略或观察入口使用的附加数据。
    """

    message: MessageChain | None = field(
        default=None,
        converter=lambda value: MessageChain.assign(value) if value is not None else None,
    )
    scope: StopScope = StopScope.CANDIDATE
    data: dict = field(factory=dict)


@define
class RecoveryProposal(HookResult):
    """恢复建议：由核心恢复协调器处理，模块不能直接调用 parser 私有函数。

    :param trigger_msg: 建议重写后的触发文本（不含前缀时由核心补前缀）。
    :param command_first_word: 建议的模块名。
    :param display: 展示给用户的命令（不含前缀）。
    :param data: 额外上下文。
    """

    trigger_msg: str
    command_first_word: str
    display: str | None = None
    data: dict = field(factory=dict)


@define
class Handled(HookResult):
    """错误/恢复入口专用：该 hook 已处理，不再走默认错误提示。"""

    data: dict = field(factory=dict)


def normalize_result(raw: object) -> HookResult:
    """把 hook 返回值归一化为类型化结果；``None`` 视为 Continue。"""
    if raw is None:
        return Continue()
    if isinstance(raw, HookResult):
        return raw
    raise TypeError(f"Invalid parser hook result type: {type(raw)!r}")


__all__ = [
    "HookResult",
    "Continue",
    "RewriteTrigger",
    "Stop",
    "StopScope",
    "RecoveryProposal",
    "Handled",
    "normalize_result",
]
