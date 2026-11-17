"""模块 hook 共用的订阅、资格过滤、runtime 调用与具名分发。"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable

from core.constants.exceptions import SendMessageFailed, SessionFinished, WaitCancelException
from core.logger import Logger
from core.module_runtime import ModuleRuntimeManager

if TYPE_CHECKING:
    from core.types import Module
    from core.types.module.component_meta import HookMeta


DEFAULT_HOOK_TIMEOUT = 5.0
PROTOCOL_EXCEPTIONS = (SessionFinished, WaitCancelException, SendMessageFailed)


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
    server_scope: bool = False

    @property
    def function(self):
        return self.meta.function


@dataclass(slots=True)
class ModuleHookDispatchOutcome:
    """具名 hook 批量分发的执行摘要。"""

    result: Any = None
    executed: int = 0
    failed: int = 0
    skipped_stale: int = 0


def subscription_sort_key(sub: HookSubscription) -> tuple[int, str, str]:
    return (sub.priority, sub.module_name, sub.subscription_id)


def platform_allows(available_for, exclude_from, target_from: str | None, client_name: str | None) -> bool:
    if not target_from:
        return True
    if not client_name:
        client_name = target_from.split("|", 1)[0] if "|" in target_from else target_from
    if target_from in exclude_from or client_name in exclude_from:
        return False
    return "*" in available_for or target_from in available_for or client_name in available_for


def current_generation(module_name: str) -> int | None:
    runtime = ModuleRuntimeManager._staging.get(module_name) or ModuleRuntimeManager._current.get(module_name)
    return runtime.generation if runtime is not None else None


def _module_context_enabled(module: "Module", module_name: str, session_info) -> bool:
    if module.base:
        return True
    if not getattr(session_info, "require_enable_modules", True):
        return True
    enabled = getattr(session_info, "enabled_modules", None)
    if enabled is None:
        return True
    return module_name in enabled


class HookExecutor:
    """共享订阅资格判断；具体 hook 系统只实现自身的结果协议。"""

    def __init__(self, modules_manager: Any):
        self._modules_manager = modules_manager

    @staticmethod
    def _module_active(module: "Module") -> bool:
        return bool(module._db_load and module.load)

    @staticmethod
    def _generation_ok(sub: HookSubscription) -> bool:
        if sub.generation <= 0:
            return True
        generation = current_generation(sub.module_name)
        return generation is not None and generation == sub.generation

    def subscription_eligible(
        self,
        sub: HookSubscription,
        target_from: str | None,
        client_name: str | None,
        session_info: Any = None,
        *,
        check_context: bool = True,
    ) -> tuple[bool, bool]:
        """返回 ``(可执行, 代际过期)``。"""
        if not sub.load:
            return False, False
        module = self._modules_manager.modules.get(sub.module_name)
        if module is None or not self._module_active(module):
            return False, False
        if not self._generation_ok(sub):
            return False, True
        if session_info is None and ("*" not in tuple(module.available_for) or "*" not in tuple(sub.available_for)):
            return False, False
        if not platform_allows(tuple(module.available_for), tuple(module.exclude_from), target_from, client_name):
            return False, False
        if not platform_allows(sub.available_for, sub.exclude_from, target_from, client_name):
            return False, False
        if check_context and session_info is not None and not sub.server_scope:
            if not _module_context_enabled(module, sub.module_name, session_info):
                return False, False
        return True, False


async def invoke_subscription(
    sub: HookSubscription,
    context: Any,
    timeout: float | None = None,
    *,
    transform: Callable[[Any], Any] | None = None,
    task_prefix: str = "module-hook",
) -> Any:
    """在模块 runtime 中调用订阅，统一处理超时、取消和任务收尾。"""

    async def call() -> Any:
        async with ModuleRuntimeManager.use(sub.module_name):
            result = await sub.function(context)
        return transform(result) if transform is not None else result

    if timeout is None or timeout <= 0:
        return await call()

    runtime = ModuleRuntimeManager._staging.get(sub.module_name) or ModuleRuntimeManager._current.get(sub.module_name)
    if runtime is not None and runtime.active:
        task = runtime.spawn(call(), name=f"{task_prefix}:{sub.subscription_id}")
    else:
        task = asyncio.ensure_future(call())
    try:
        done, _pending = await asyncio.wait({task}, timeout=timeout)
    except asyncio.CancelledError:
        task.cancel()
        raise
    if task in done:
        return task.result()

    task.cancel()
    try:
        await asyncio.wait_for(asyncio.shield(task), timeout=0.05)
    except asyncio.CancelledError:
        if not task.cancelled():
            raise
    except (asyncio.TimeoutError, Exception):
        pass
    raise asyncio.TimeoutError()


class ModuleHookExecutor(HookExecutor):
    """具名 module hook 分发器。"""

    def _eligible(self, sub: HookSubscription, session_info: Any) -> tuple[bool, bool]:
        target_from = getattr(session_info, "target_from", None) if session_info is not None else None
        client_name = getattr(session_info, "client_name", None) if session_info is not None else None
        # 具名能力由显式名称调用，不要求目标场景启用该模块。
        return self.subscription_eligible(sub, target_from, client_name, check_context=False)

    def _subscriptions(self, hook_name: str, module_trigger: bool) -> list[HookSubscription]:
        index_name = "module_hook_subscriptions" if module_trigger else "modules_hook_subscriptions"
        subscriptions = getattr(self._modules_manager, index_name, {}).get(hook_name, ())
        return sorted(subscriptions, key=subscription_sort_key)

    async def dispatch_outcome(
        self,
        hook_name: str,
        session_info: Any = None,
        args: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> ModuleHookDispatchOutcome:
        if not hook_name:
            raise ValueError("Invalid hook name")

        module_name = hook_name.split(".", 1)[0]
        module_trigger = "." not in hook_name
        if module_name not in self._modules_manager.modules:
            raise ValueError(f"Invalid module name {module_name}")

        subscriptions = self._subscriptions(module_name if module_trigger else hook_name, module_trigger)
        if not module_trigger and not subscriptions:
            raise ValueError(f"Invalid hook name {hook_name}")

        from core.builtins.session.info import ModuleHookContext

        outcome = ModuleHookDispatchOutcome()
        hook_args = dict(args or {})
        for sub in subscriptions:
            eligible, stale = self._eligible(sub, session_info)
            outcome.skipped_stale += int(stale)
            if not eligible:
                continue

            # 每个回调拿到独立参数字典，广播 hook 的就地修改不会污染后续回调。
            context = ModuleHookContext(dict(hook_args), session_info=session_info)
            budget = sub.timeout if timeout is None else timeout
            try:
                result = await invoke_subscription(sub, context, budget)
            except asyncio.CancelledError:
                raise
            except (SystemExit, KeyboardInterrupt):
                raise
            except PROTOCOL_EXCEPTIONS as exc:
                outcome.failed += 1
                if not module_trigger:
                    raise
                Logger.warning(
                    f"Module hook {sub.subscription_id} raised protocol exception {type(exc).__name__}; skipped."
                )
                continue
            except Exception:
                outcome.failed += 1
                if not module_trigger:
                    raise
                Logger.exception(f"Module hook {sub.subscription_id} failed; skipped.")
                continue

            outcome.executed += 1
            outcome.result = result
        return outcome

    async def dispatch(
        self,
        hook_name: str,
        session_info: Any = None,
        args: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> Any:
        outcome = await self.dispatch_outcome(hook_name, session_info=session_info, args=args, timeout=timeout)
        return None if "." not in hook_name else outcome.result


def build_subscription(module_name: str, meta: "HookMeta", index: int) -> HookSubscription:
    subscription_id = (
        meta.point + ":" + (meta.name or f"anon#{index}")
        if meta.point
        else module_name + ":" + (meta.name or f"anon#{index}")
    )
    return HookSubscription(
        module_name=module_name,
        subscription_id=subscription_id,
        meta=meta,
        priority=meta.priority,
        available_for=tuple(meta.available_for),
        exclude_from=tuple(meta.exclude_from),
        load=meta.load,
        timeout=float(meta.timeout) if meta.timeout is not None else DEFAULT_HOOK_TIMEOUT,
        generation=current_generation(module_name) or 0,
        server_scope=bool(getattr(meta, "server_scope", False)),
    )
