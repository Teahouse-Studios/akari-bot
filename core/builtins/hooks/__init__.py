"""模块 hook 的共享执行基础与具名分发器。"""

from .executor import (
    DEFAULT_HOOK_TIMEOUT,
    HookExecutor,
    HookSubscription,
    ModuleHookDispatchOutcome,
    ModuleHookExecutor,
    build_subscription,
    current_generation,
    invoke_subscription,
    platform_allows,
    subscription_sort_key,
)
from .dispatch import (
    dispatch_module_hook,
    dispatch_module_hook_outcome,
    get_module_hook_executor,
    reset_module_hook_executor,
)

__all__ = [
    "DEFAULT_HOOK_TIMEOUT",
    "HookExecutor",
    "HookSubscription",
    "ModuleHookDispatchOutcome",
    "ModuleHookExecutor",
    "build_subscription",
    "current_generation",
    "dispatch_module_hook",
    "dispatch_module_hook_outcome",
    "get_module_hook_executor",
    "invoke_subscription",
    "platform_allows",
    "reset_module_hook_executor",
    "subscription_sort_key",
]
