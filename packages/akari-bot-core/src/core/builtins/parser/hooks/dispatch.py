"""parser / 出站内部使用的入口分发便捷函数。"""

from __future__ import annotations

from contextvars import ContextVar
from typing import TYPE_CHECKING, Any

from core.constants.exceptions import SendMessageFailed, SessionFinished, WaitCancelException
from core.loader import ModulesManager
from core.logger import Logger

from .context import OutgoingPayload
from .executor import HookDispatchOutcome, ParserHookExecutor
from .points import HookPoint
from .results import Continue, HookResult, Stop

if TYPE_CHECKING:
    from core.builtins.bot import Bot

_executor: ParserHookExecutor | None = None

# 出站递归防护：before_send 内再 send 时跳过嵌套 before_send 改写
_outgoing_dispatching: ContextVar[bool] = ContextVar("outgoing_dispatching", default=False)
# 结果观察递归防护
_outgoing_observing: ContextVar[bool] = ContextVar("outgoing_observing", default=False)


def get_parser_hook_executor() -> ParserHookExecutor:
    global _executor
    if _executor is None:
        _executor = ParserHookExecutor(ModulesManager)
    return _executor


def has_hook_subscribers(point: HookPoint) -> bool:
    return get_parser_hook_executor().has_subscribers(point)


async def dispatch_parser_hook(
    point: HookPoint,
    msg: "Bot.MessageSession",
    *,
    module_name: str | None = None,
    command_first_word: str | None = None,
    data: dict[str, Any] | None = None,
    outgoing: OutgoingPayload | None = None,
) -> HookDispatchOutcome:
    return await get_parser_hook_executor().dispatch(
        point,
        msg,
        module_name=module_name,
        command_first_word=command_first_word,
        data=data,
        outgoing=outgoing,
    )


def is_outgoing_dispatching() -> bool:
    return _outgoing_dispatching.get()


async def dispatch_outgoing_before_send(msg: "Bot.MessageSession", payload: OutgoingPayload) -> Stop | None:
    """出站改写；返回 Stop 表示取消本次发送。"""
    if is_outgoing_dispatching() or not has_hook_subscribers(HookPoint.OUTGOING_BEFORE_SEND):
        return None
    token = _outgoing_dispatching.set(True)
    try:
        outcome = await dispatch_parser_hook(
            HookPoint.OUTGOING_BEFORE_SEND,
            msg,
            data={"forbid_nested_send": True},
            outgoing=payload,
        )
        return outcome.result if isinstance(outcome.result, Stop) else None
    finally:
        _outgoing_dispatching.reset(token)


async def dispatch_outgoing_result(
    msg: "Bot.MessageSession",
    payload: OutgoingPayload,
    *,
    ok: bool,
    message_ids: list | str | int | None = None,
) -> None:
    """隔离快照与观察失败，保留实际发送结果；取消与进程退出仍向外传播。"""
    point = HookPoint.OUTGOING_SENT if ok else HookPoint.OUTGOING_FAILED
    if _outgoing_observing.get():
        return
    token = _outgoing_observing.set(True)
    try:
        if not has_hook_subscribers(point):
            return
        snapshot = payload.snapshot()
        if message_ids is not None:
            ids = message_ids if isinstance(message_ids, list) else [message_ids]
            snapshot.message_ids = [str(message_id) for message_id in ids]
        await dispatch_parser_hook(point, msg, data={"ok": ok}, outgoing=snapshot)
    except (Exception, SessionFinished, WaitCancelException, SendMessageFailed):
        Logger.exception(f"Outgoing observer at {point} failed; the platform result is unchanged.")
    finally:
        _outgoing_observing.reset(token)


def reset_parser_hook_executor() -> None:
    """测试用：丢弃单例，便于替换 ModulesManager。"""
    global _executor
    _executor = None


__all__ = [
    "get_parser_hook_executor",
    "has_hook_subscribers",
    "dispatch_parser_hook",
    "dispatch_outgoing_before_send",
    "dispatch_outgoing_result",
    "is_outgoing_dispatching",
    "reset_parser_hook_executor",
    "Continue",
    "HookResult",
]
