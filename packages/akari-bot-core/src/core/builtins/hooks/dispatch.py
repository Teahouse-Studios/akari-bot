"""具名 module hook 的全局分发入口。"""

from __future__ import annotations

from typing import Any

from core.loader import ModulesManager

from .executor import ModuleHookExecutor

_executor: ModuleHookExecutor | None = None


def get_module_hook_executor() -> ModuleHookExecutor:
    global _executor
    if _executor is None:
        _executor = ModuleHookExecutor(ModulesManager)
    return _executor


async def dispatch_module_hook(
    hook_name: str,
    *,
    session_info: Any = None,
    args: dict[str, Any] | None = None,
    timeout: float | None = None,
) -> Any:
    return await get_module_hook_executor().dispatch(
        hook_name,
        session_info=session_info,
        args=args,
        timeout=timeout,
    )


async def dispatch_module_hook_outcome(
    hook_name: str,
    *,
    session_info: Any = None,
    args: dict[str, Any] | None = None,
    timeout: float | None = None,
):
    """返回具名 hook 的执行摘要，供诊断和测试使用。"""
    return await get_module_hook_executor().dispatch_outcome(
        hook_name,
        session_info=session_info,
        args=args,
        timeout=timeout,
    )


def reset_module_hook_executor() -> None:
    global _executor
    _executor = None


__all__ = [
    "dispatch_module_hook",
    "dispatch_module_hook_outcome",
    "get_module_hook_executor",
    "reset_module_hook_executor",
]
