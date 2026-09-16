"""Parser / 出站入口 hook 执行器。

契约见 README。关键点：
- 订阅 generation 优先取 staging（reload commit 前 refresh）
- 观察入口不接受控制结果
- 超时/失败丢弃草稿与控制结果
- 出站 before_send 逐 hook 草稿提交
"""

from __future__ import annotations

import asyncio
import time
from contextvars import ContextVar
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from core.constants.exceptions import SendMessageFailed, SessionFinished, WaitCancelException
from core.logger import Logger
from core.module_runtime import ModuleRuntimeManager

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
    from core.types import Module
    from core.types.module.component_meta import HookMeta

DEFAULT_HOOK_TIMEOUT = 5.0

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


@dataclass(frozen=True, slots=True)
class HookSubscription:
    module_name: str
    subscription_id: str
    meta: "HookMeta"
    priority: int
    available_for: tuple[str, ...]
    exclude_from: tuple[str, ...]
    load: bool
    timeout: float = DEFAULT_HOOK_TIMEOUT
    generation: int = 0
    # server 作用域：免场景 enabled_modules，仍遵守全局停用与平台约束
    server_scope: bool = False

    @property
    def function(self):
        return self.meta.function


@dataclass(slots=True)
class HookDispatchOutcome:
    result: HookResult
    executed: int = 0
    failed: int = 0
    skipped_stale: int = 0


def _subscription_sort_key(sub: HookSubscription) -> tuple[int, str, str]:
    return (sub.priority, sub.module_name, sub.subscription_id)


def _platform_allows(available_for, exclude_from, target_from: str | None, client_name: str | None) -> bool:
    if not target_from:
        return True
    if not client_name:
        client_name = target_from.split("|", 1)[0] if "|" in target_from else target_from
    if target_from in exclude_from or client_name in exclude_from:
        return False
    return "*" in available_for or target_from in available_for or client_name in available_for


def _current_generation(module_name: str) -> int | None:
    # reload 期间新 runtime 在 staging；必须优先取它
    runtime = ModuleRuntimeManager._staging.get(module_name) or ModuleRuntimeManager._current.get(module_name)
    return runtime.generation if runtime is not None else None


def _module_scene_enabled(module: "Module", module_name: str, session_info) -> bool:
    if module.base:
        return True
    # 与 parser 一致：不要求场景启用时不拦截
    if not getattr(session_info, "require_enable_modules", True):
        return True
    enabled = getattr(session_info, "enabled_modules", None)
    if enabled is None:
        return True
    return module_name in enabled


class ParserHookExecutor:
    def __init__(self, modules_manager: Any):
        self._modules_manager = modules_manager

    def has_subscribers(self, point: HookPoint) -> bool:
        return bool(self._modules_manager.parser_hook_subscriptions.get(point))

    def _module_active(self, module: "Module") -> bool:
        return bool(module._db_load and module.load)

    def _generation_ok(self, sub: HookSubscription) -> bool:
        if sub.generation <= 0:
            return True
        current = _current_generation(sub.module_name)
        return current is not None and current == sub.generation

    def _subscription_eligible(
        self,
        sub: HookSubscription,
        target_from: str | None,
        client_name: str | None,
        session_info: Any = None,
    ) -> tuple[bool, bool]:
        """判断订阅当前是否可执行，并标记代际是否已过期。"""
        if not sub.load:
            return False, False
        module = self._modules_manager.modules.get(sub.module_name)
        if module is None or not self._module_active(module):
            return False, False
        if not self._generation_ok(sub):
            return False, True
        if not _platform_allows(tuple(module.available_for), tuple(module.exclude_from), target_from, client_name):
            return False, False
        if not _platform_allows(sub.available_for, sub.exclude_from, target_from, client_name):
            return False, False
        if session_info is not None and not sub.server_scope:
            if not _module_scene_enabled(module, sub.module_name, session_info):
                return False, False
        return True, False

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
        selected.sort(key=_subscription_sort_key)
        return selected, stale

    def _result_allowed(self, point: HookPoint, result: HookResult) -> bool:
        allowed = _ALLOWED_RESULTS.get(point)
        if not allowed:
            return True
        return isinstance(result, allowed)

    def _result_fields_valid(self, result: HookResult) -> bool:
        """控制结果的字段必须在 hook 边界校验，不能让核心承担后续类型错误。"""
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
        async def call() -> HookResult:
            async with ModuleRuntimeManager.use(sub.module_name):
                raw = await sub.function(ctx)
            return normalize_result(raw)

        if timeout is None or timeout <= 0:
            return await call()

        runtime = ModuleRuntimeManager._staging.get(sub.module_name) or ModuleRuntimeManager._current.get(
            sub.module_name
        )
        # 子任务必须由模块 runtime 托管：dispatch 被取消或 hook 超时时随之取消，
        # 不会在调用方结束后游离执行；runtime 缺失或已停用时退回普通任务。
        if runtime is not None and runtime.active:
            task = runtime.spawn(call(), name=f"parser-hook:{sub.subscription_id}")
        else:
            task = asyncio.ensure_future(call())
        try:
            done, _pending = await asyncio.wait({task}, timeout=timeout)
        except asyncio.CancelledError:
            task.cancel()
            raise
        if task in done:
            return task.result()
        # 截止：撤销提交资格并有界收尾；吞取消后的晚返回一概不采纳
        task.cancel()
        try:
            # 只等子任务自身的收尾；收尾期间父 dispatch 被外部取消时继续传播，
            # 不能把这次取消吞成可忽略的 TimeoutError。
            await asyncio.wait_for(asyncio.shield(task), timeout=0.05)
        except asyncio.CancelledError:
            if not task.cancelled():
                raise
        except (asyncio.TimeoutError, Exception):
            pass
        raise asyncio.TimeoutError()


def build_subscription(module_name: str, meta: "HookMeta", index: int) -> HookSubscription:
    subscription_id = meta.point + ":" + (meta.name or f"anon#{index}")
    generation = _current_generation(module_name) or 0
    server_scope = bool(getattr(meta, "server_scope", False))
    return HookSubscription(
        module_name=module_name,
        subscription_id=subscription_id,
        meta=meta,
        priority=meta.priority,
        available_for=tuple(meta.available_for),
        exclude_from=tuple(meta.exclude_from),
        load=meta.load,
        timeout=float(meta.timeout) if meta.timeout is not None else DEFAULT_HOOK_TIMEOUT,
        generation=generation,
        server_scope=server_scope,
    )


__all__ = [
    "DEFAULT_HOOK_TIMEOUT",
    "HookSubscription",
    "HookDispatchOutcome",
    "ParserHookExecutor",
    "build_subscription",
]
