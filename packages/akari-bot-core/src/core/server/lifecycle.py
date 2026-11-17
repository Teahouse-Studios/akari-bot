"""Server 进程内后台资源的统一关闭注册表。"""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from core.logger import Logger


@dataclass(frozen=True, slots=True)
class BackgroundCleanupSpec:
    """一项需要在 Queue 和数据库关闭前执行的后台资源清理。"""

    callback: Callable[[], Awaitable[None]]
    label: str
    timeout: float


class BackgroundTaskLifecycle:
    """管理模块和核心组件持有的 detached 后台任务。"""

    _cleanup_hooks: dict[str, BackgroundCleanupSpec] = {}

    @classmethod
    def register_cleanup(
        cls,
        key: str,
        callback: Callable[[], Awaitable[None]],
        *,
        label: str | None = None,
        timeout: float = 10,
    ) -> None:
        """注册一项幂等清理；相同稳定 key 的热重载会原位替换旧回调。"""
        if not key:
            raise ValueError("Background cleanup key cannot be empty.")
        if timeout <= 0:
            raise ValueError("Background cleanup timeout must be positive.")
        cls._cleanup_hooks[key] = BackgroundCleanupSpec(
            callback=callback,
            label=label or key,
            timeout=timeout,
        )

    @classmethod
    async def run_cleanup(cls) -> None:
        """按注册顺序执行全部清理，并隔离单项超时或失败。"""
        for spec in tuple(cls._cleanup_hooks.values()):
            try:
                await asyncio.wait_for(spec.callback(), timeout=spec.timeout)
            except asyncio.CancelledError:
                raise
            except TimeoutError:
                Logger.warning(f"Timed out while cancelling {spec.label}.")
            except Exception:
                Logger.exception(f"Failed to cancel {spec.label} cleanly.")


__all__ = ["BackgroundCleanupSpec", "BackgroundTaskLifecycle"]
