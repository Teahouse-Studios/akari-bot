"""Parser / 出站入口 hook 执行器。"""

from __future__ import annotations

import asyncio
import time
from contextvars import ContextVar
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from core.builtins.hooks import (
    DEFAULT_HOOK_TIMEOUT,
    HookExecutor,
    HookSubscription,
    build_subscription,
    invoke_subscription,
    subscription_sort_key,
)
from core.constants.exceptions import SendMessageFailed, SessionFinished, WaitCancelException
from core.logger import Logger

from core.builtins.message.chain import MessageChain

from .context import OutgoingPayload, ParserHookContext
from .draft import SessionDraft, build_session_draft
from .points import SESSION_DRAFT_POINTS, HookPoint
from .results import (
    Continue,
    Handled,
    HookResult,
    RecoveryProposal,
    RewriteTrigger,
    Stop,
    StopScope,
    normalize_result,
)

if TYPE_CHECKING:
    from core.builtins.bot import Bot

_CONTROL_RESULTS = (Stop, RecoveryProposal, Handled)
_PROTOCOL_EXCEPTIONS = (SessionFinished, WaitCancelException, SendMessageFailed)

# 同一会话的嵌套分发：父 hook 仍在执行时，子 dispatch 直接跳过，避免子事务提交后父失败无法撤销
_active_dispatch: ContextVar[tuple[int, HookPoint] | None] = ContextVar("parser_hook_active_dispatch", default=None)

# 观察入口：禁止控制结果短路
_OBSERVER_POINTS = frozenset(
    {
        HookPoint.EXECUTION_FINISHED,
        HookPoint.FINISHED,
        HookPoint.OUTGOING_SENT,
        HookPoint.OUTGOING_FAILED,
    }
)

# 每入口允许的结果类型；未列出的入口允许全部
_ALLOWED_RESULTS: dict[HookPoint, tuple[type, ...]] = {
    HookPoint.SESSION_READY: (Continue, Stop),
    HookPoint.SESSION_BEFORE_WAIT: (Continue, Stop),
    HookPoint.MESSAGE_NORMALIZED: (Continue, RewriteTrigger, Stop),
    HookPoint.COMMAND_PREPARE: (Continue, Stop),
    HookPoint.COMMAND_BEFORE_PARSE: (Continue, Stop),
    HookPoint.COMMAND_BEFORE_EXECUTE: (Continue, Stop),
    HookPoint.COMMAND_ROUTE: (Continue, Stop),
    HookPoint.COMMAND_UNMATCHED: (Continue, Stop, RecoveryProposal, Handled),
    HookPoint.REGEX_ROUTE: (Continue, Stop),
    HookPoint.REGEX_CANDIDATE: (Continue, Stop),
    HookPoint.CHANNEL_CLAIM: (Continue, Stop),
    HookPoint.REGEX_PREPARE: (Continue, Stop),
    HookPoint.REGEX_BEFORE_EXECUTE: (Continue, Stop),
    HookPoint.EXECUTION_FINISHED: (Continue,),
    HookPoint.EXECUTION_ERROR: (Continue, Handled),
    HookPoint.FINISHED: (Continue,),
    HookPoint.OUTGOING_BEFORE_SEND: (Continue, Stop),
    HookPoint.OUTGOING_SENT: (Continue,),
    HookPoint.OUTGOING_FAILED: (Continue,),
}


@dataclass(slots=True)
class HookDispatchOutcome:
    result: HookResult
    executed: int = 0
    failed: int = 0
    skipped_stale: int = 0


class ParserHookExecutor(HookExecutor):
    def __init__(self, modules_manager: Any):
        super().__init__(modules_manager)

    def has_subscribers(self, point: HookPoint) -> bool:
        return bool(self._modules_manager.parser_hook_subscriptions.get(point))

    def _subscription_eligible(
        self,
        sub: HookSubscription,
        target_from: str | None,
        client_name: str | None,
        session_info: Any = None,
    ) -> tuple[bool, bool]:
        return self.subscription_eligible(sub, target_from, client_name, session_info)

    def _collect(
        self,
        point: HookPoint,
        target_from: str | None,
        client_name: str | None,
        session_info: Any = None,
    ) -> tuple[list[HookSubscription], int]:
        raw = self._modules_manager.parser_hook_subscriptions.get(point)
        if not raw:
            return [], 0
        selected: list[HookSubscription] = []
        stale = 0
        for sub in raw:
            eligible, is_stale = self._subscription_eligible(sub, target_from, client_name, session_info)
            stale += int(is_stale)
            if eligible:
                selected.append(sub)
        selected.sort(key=subscription_sort_key)
        return selected, stale

    def _result_allowed(self, point: HookPoint, result: HookResult) -> bool:
        allowed = _ALLOWED_RESULTS.get(point)
        if not allowed:
            return True
        return isinstance(result, allowed)

    def _result_fields_valid(self, result: HookResult) -> bool:
        if isinstance(result, RecoveryProposal):
            return (
                isinstance(result.trigger_msg, str)
                and isinstance(result.command_first_word, str)
                and (result.display is None or isinstance(result.display, str))
            )
        if isinstance(result, RewriteTrigger):
            return isinstance(result.trigger_msg, str)
        if isinstance(result, Stop):
            return (
                (result.message is None or isinstance(result.message, MessageChain))
                and isinstance(result.scope, StopScope)
                and isinstance(result.data, dict)
            )
        if isinstance(result, Handled):
            return isinstance(result.data, dict)
        if isinstance(result, Continue):
            return isinstance(result.data, dict)
        return False

    async def dispatch(
        self,
        point: HookPoint,
        msg: "Bot.MessageSession",
        *,
        module_name: str | None = None,
        command_first_word: str | None = None,
        data: dict[str, Any] | None = None,
        timeout: float | None = None,
        outgoing: OutgoingPayload | None = None,
    ) -> HookDispatchOutcome:
        session_info = msg.session_info
        # 父 hook 尚未结束时拒绝同会话的嵌套分发：子事务的提交无法随父失败撤销。
        active = _active_dispatch.get()
        if active is not None and active[0] == id(session_info):
            Logger.warning(f"Nested parser hook dispatch for the same session skipped at {point} (active={active[1]}).")
            return HookDispatchOutcome(result=Continue())
        subscriptions, stale = self._collect(point, session_info.target_from, session_info.client_name, session_info)
        outcome = HookDispatchOutcome(result=Continue(), skipped_stale=stale)
        if not subscriptions:
            return outcome

        dispatch_token = _active_dispatch.set((id(session_info), point))
        try:
            use_draft = point in SESSION_DRAFT_POINTS
            is_observer = point in _OBSERVER_POINTS
            shared_data = dict(data or {})
            for sub in subscriptions:
                # 前序 hook 等待期间可能停用或重载后续订阅方；调用前必须按最新状态复核。
                eligible, is_stale = self._subscription_eligible(
                    sub,
                    session_info.target_from,
                    session_info.client_name,
                    session_info,
                )
                outcome.skipped_stale += int(is_stale)
                if not eligible:
                    continue
                # 快照构建也在 hook 边界内：克隆失败按当前 hook 失败处理，不得中断后续 hook
                try:
                    draft: SessionDraft | None = build_session_draft(session_info) if use_draft else None
                    outgoing_draft: OutgoingPayload | None = outgoing.snapshot() if outgoing is not None else None
                except Exception:
                    outcome.failed += 1
                    Logger.exception(f"Parser hook {sub.subscription_id} ({point}) snapshot build failed; skipped.")
                    continue

                ctx = ParserHookContext(
                    point=point,
                    msg=msg,
                    module_name=module_name,
                    data=dict(shared_data),
                    command_first_word=command_first_word,
                    draft=draft,
                    outgoing=outgoing_draft if outgoing_draft is not None else outgoing,
                )
                budget = sub.timeout if timeout is None else timeout
                started = time.perf_counter()
                timed_out = False
                try:
                    result = await self._invoke(sub, ctx, budget)
                except asyncio.CancelledError:
                    if draft is not None:
                        draft.revoke()
                    raise
                except (SystemExit, KeyboardInterrupt):
                    if draft is not None:
                        draft.revoke()
                    raise
                except _PROTOCOL_EXCEPTIONS as exc:
                    if draft is not None:
                        draft.revoke()
                    outcome.failed += 1
                    Logger.warning(
                        f"Parser hook {sub.subscription_id} ({point}) raised protocol exception "
                        f"{type(exc).__name__}; treated as failure and discarded."
                    )
                    continue
                except asyncio.TimeoutError:
                    timed_out = True
                    result = Continue()
                except Exception:
                    if draft is not None:
                        draft.revoke()
                    outcome.failed += 1
                    Logger.exception(f"Parser hook {sub.subscription_id} ({point}) failed in module {sub.module_name}.")
                    continue

                elapsed = time.perf_counter() - started
                if timed_out:
                    if draft is not None:
                        draft.revoke()
                    outcome.failed += 1
                    Logger.warning(f"Parser hook {sub.subscription_id} timed out; result discarded.")
                    continue
                if budget is not None and budget > 0 and elapsed > budget:
                    Logger.warning(f"Parser hook {sub.subscription_id} ({point}) took {elapsed:.3f}s.")

                # 观察入口：控制结果视为失败，不短路
                if is_observer and isinstance(result, _CONTROL_RESULTS):
                    if draft is not None:
                        draft.revoke()
                    outcome.failed += 1
                    Logger.warning(f"Observer hook {sub.subscription_id} returned {type(result).__name__}; discarded.")
                    continue
                if not self._result_allowed(point, result) or not self._result_fields_valid(result):
                    if draft is not None:
                        draft.revoke()
                    outcome.failed += 1
                    Logger.warning(
                        f"Parser hook {sub.subscription_id} returned invalid {type(result).__name__} for {point}."
                    )
                    continue

                if draft is not None:
                    try:
                        draft.commit()
                    except Exception:
                        draft.revoke()
                        outcome.failed += 1
                        Logger.exception(f"Parser hook {sub.subscription_id} ({point}) draft commit failed; discarded.")
                        continue

                if isinstance(result, Continue):
                    # Continue carries optional stage metadata (for example, whether
                    # the wait-task router should be skipped). Preserve contributions
                    # from every subscriber instead of letting the last one overwrite them.
                    if result.data:
                        shared_data.update(result.data)
                        outcome.result = Continue(data=dict(shared_data))
                elif isinstance(result, RewriteTrigger):
                    msg.trigger_msg = result.trigger_msg
                if outgoing is not None and outgoing_draft is not None and point == HookPoint.OUTGOING_BEFORE_SEND:
                    if isinstance(result, Continue):
                        try:
                            outgoing.apply_from(outgoing_draft)
                        except Exception:
                            outcome.failed += 1
                            Logger.exception(
                                f"Parser hook {sub.subscription_id} ({point}) outgoing commit failed; discarded."
                            )
                            continue

                outcome.executed += 1
                if isinstance(result, _CONTROL_RESULTS) and not is_observer:
                    outcome.result = result
                    return outcome
            return outcome
        finally:
            _active_dispatch.reset(dispatch_token)

    async def _invoke(
        self,
        sub: HookSubscription,
        ctx: ParserHookContext,
        timeout: float | None,
    ) -> HookResult:
        return await invoke_subscription(
            sub,
            ctx,
            timeout,
            transform=normalize_result,
            task_prefix="parser-hook",
        )


__all__ = [
    "DEFAULT_HOOK_TIMEOUT",
    "HookSubscription",
    "HookDispatchOutcome",
    "ParserHookExecutor",
    "build_subscription",
]
