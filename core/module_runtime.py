"""Framework-managed module runtime resources.

Modules declare long-lived state, resources and background tasks through the
``Bind.Module`` helpers. The framework owns their lifecycle across enable,
disable, reload and shutdown transitions.
"""

from __future__ import annotations

import asyncio
import inspect
import re
import shutil
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Generic, TypeVar

from core.constants.path import cache_path
from core.logger import Logger


T = TypeVar("T")
_MISSING = object()


@dataclass(slots=True)
class _StateSpec(Generic[T]):
    name: str
    default_factory: Callable[[], T]
    preserve: bool
    version: int
    migrate: Callable[[Any], T] | None = None


@dataclass(slots=True)
class _CleanupSpec:
    callback: Callable[[], Any | Awaitable[Any]]
    name: str
    timeout: float


class RuntimeResource(Generic[T]):
    """A lazily-created resource owned by one module runtime generation."""

    def __init__(
        self,
        runtime: "ModuleRuntime",
        name: str,
        factory: Callable[[], T | Awaitable[T]],
        close: Callable[[T], Any | Awaitable[Any]] | None,
        *,
        timeout: float,
    ):
        self.runtime = runtime
        self.name = name
        self.factory = factory
        self.close_callback = close
        self.timeout = timeout
        self.value: T | None = None
        self.initialized = False
        self._lock = asyncio.Lock()

    async def get(self) -> T:
        """Return the initialized resource, creating it on first access."""
        if not self.runtime.active:
            raise RuntimeError(f"Module {self.runtime.module_name!r} is not active.")
        if self.initialized:
            return self.value  # type: ignore[return-value]
        async with self._lock:
            if self.initialized:
                return self.value  # type: ignore[return-value]
            value = self.factory()
            if inspect.isawaitable(value):
                value = await value
            self.value = value
            self.initialized = True
            return value

    async def close(self) -> None:
        """Close the resource if it was initialized."""
        async with self._lock:
            if not self.initialized:
                return
            value = self.value
            self.value = None
            self.initialized = False
            close = self.close_callback
            if close is None:
                close = getattr(value, "aclose", None) or getattr(value, "close", None)
            if close is None:
                return
            try:
                result = close(value)
                if inspect.isawaitable(result):
                    await asyncio.wait_for(result, timeout=self.timeout)
            except asyncio.CancelledError:
                raise
            except Exception:
                Logger.exception(f"Failed to close resource {self.name!r} for module {self.runtime.module_name!r}:")


@dataclass(slots=True, eq=False)
class ModuleRuntime:
    """Runtime state for one module generation."""

    module_name: str
    generation: int = 1
    active: bool = True
    state: dict[str, Any] = field(default_factory=dict)
    state_specs: dict[str, _StateSpec] = field(default_factory=dict)
    resources: dict[str, RuntimeResource] = field(default_factory=dict)
    cache_paths: dict[str, Path] = field(default_factory=dict)
    tasks: set[asyncio.Task] = field(default_factory=set)
    suppressed_task_errors: dict[asyncio.Task, tuple[type[BaseException], ...]] = field(default_factory=dict)
    cleanup_specs: list[_CleanupSpec] = field(default_factory=list)
    _stop_lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)

    def next_generation(self) -> "ModuleRuntime":
        """Create the next generation while retaining declared state metadata."""
        return ModuleRuntime(
            module_name=self.module_name,
            generation=self.generation + 1,
            state=dict(self.state),
            state_specs=dict(self.state_specs),
        )

    def get_state(
        self,
        name: str,
        *,
        default_factory: Callable[[], T],
        preserve: bool,
        version: int,
        migrate: Callable[[Any], T] | None,
    ) -> T:
        """Resolve a declared state object for the current generation."""
        previous_spec = self.state_specs.get(name)
        previous = self.state.get(name, _MISSING)
        value: Any
        if preserve and previous is not _MISSING:
            if previous_spec is not None and previous_spec.version != version:
                if migrate is None:
                    value = default_factory()
                else:
                    value = migrate(previous)
            else:
                value = previous
        else:
            value = default_factory()
        self.state[name] = value
        self.state_specs[name] = _StateSpec(name, default_factory, preserve, version, migrate)
        return value

    def declare_resource(
        self,
        name: str,
        factory: Callable[[], T | Awaitable[T]],
        close: Callable[[T], Any | Awaitable[Any]] | None,
        *,
        timeout: float,
    ) -> RuntimeResource[T]:
        """Declare a lazy resource for this generation."""
        if name in self.resources:
            raise ValueError(f"Module {self.module_name!r} declares resource {name!r} more than once.")
        resource = RuntimeResource(self, name, factory, close, timeout=timeout)
        self.resources[name] = resource
        return resource

    def declare_cache_path(self, name: str, version: int) -> Path:
        """Return a versioned module cache directory owned by this generation."""
        if not name or version < 1:
            raise ValueError("Cache name must be nonempty and version must be positive.")
        safe_module = re.sub(r"[^A-Za-z0-9_.-]+", "_", self.module_name)
        safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", name)
        path = cache_path / "module_runtime" / safe_module / safe_name / f"v{version}"
        path.mkdir(parents=True, exist_ok=True)
        self.cache_paths[name] = path
        return path

    def declare_cleanup(
        self,
        callback: Callable[[], Any | Awaitable[Any]],
        *,
        name: str | None = None,
        timeout: float,
    ) -> None:
        if timeout <= 0:
            raise ValueError("Cleanup timeout must be positive.")
        self.cleanup_specs.append(_CleanupSpec(callback, name or f"{self.module_name}:cleanup", timeout))

    def cleanup_cache_paths(self) -> None:
        """Remove directories created for this discarded generation."""
        for path in self.cache_paths.values():
            try:
                shutil.rmtree(path, ignore_errors=True)
            except OSError:
                Logger.exception(f"Failed to clean cache directory {path} for module {self.module_name!r}:")

    def spawn(
        self,
        awaitable: Awaitable[T],
        *,
        name: str | None = None,
        suppress_errors: tuple[type[BaseException], ...] = (),
    ) -> asyncio.Task[T]:
        """Create a tracked task owned by this module generation."""
        if not self.active:
            raise RuntimeError(f"Module {self.module_name!r} is not active.")
        task = asyncio.create_task(
            awaitable,
            name=name or f"module:{self.module_name}:g{self.generation}",
        )
        self.tasks.add(task)
        if suppress_errors:
            self.suppressed_task_errors[task] = suppress_errors
        task.add_done_callback(self._task_done)
        return task

    def _task_done(self, task: asyncio.Task) -> None:
        self.tasks.discard(task)
        suppressed = self.suppressed_task_errors.pop(task, ())
        if task.cancelled():
            return
        error = task.exception()
        if error is not None and not isinstance(error, suppressed):
            Logger.error(f"Module runtime task {task.get_name()!r} failed: {error!r}")

    def activate(self) -> None:
        self.active = True

    async def stop(self, reason: str) -> None:
        """Cancel owned tasks and close resources; safe to call more than once."""
        async with self._stop_lock:
            if not self.active and not self.tasks:
                return
            self.active = False
            current = asyncio.current_task()
            tasks = [task for task in self.tasks if task is not current and not task.done()]
            for task in tasks:
                task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            self.tasks.difference_update(tasks)
            for spec in reversed(self.cleanup_specs):
                try:
                    result = spec.callback()
                    if inspect.isawaitable(result):
                        await asyncio.wait_for(result, timeout=spec.timeout)
                except asyncio.CancelledError:
                    raise
                except TimeoutError:
                    Logger.warning(f"Timed out while cleaning {spec.name!r} for module {self.module_name!r}.")
                except Exception:
                    Logger.exception(f"Failed to clean {spec.name!r} for module {self.module_name!r}:")
            for resource in reversed(tuple(self.resources.values())):
                await resource.close()
            Logger.debug(
                f"Stopped module runtime {self.module_name!r} (generation {self.generation}, reason={reason})."
            )


current_runtime: ContextVar[ModuleRuntime | None] = ContextVar("module_runtime", default=None)


class ModuleRuntimeManager:
    """Owns module runtime generations and cross-module transitions."""

    _current: dict[str, ModuleRuntime] = {}
    _staging: dict[str, ModuleRuntime] = {}

    @classmethod
    def get_or_create(cls, module_name: str) -> ModuleRuntime:
        runtime = cls._staging.get(module_name)
        if runtime is None:
            runtime = cls._current.get(module_name)
        if runtime is None:
            runtime = ModuleRuntime(module_name)
            cls._current[module_name] = runtime
        return runtime

    @classmethod
    def state(
        cls,
        module_name: str,
        name: str,
        *,
        default: T | None = None,
        default_factory: Callable[[], T] | None = None,
        preserve: bool = False,
        version: int = 1,
        migrate: Callable[[Any], T] | None = None,
    ) -> T:
        if default is not None and default_factory is not None:
            raise ValueError("Specify either default or default_factory, not both.")
        if default_factory is None:

            def default_factory() -> T:
                return default  # type: ignore[return-value]

        return cls.get_or_create(module_name).get_state(
            name,
            default_factory=default_factory,
            preserve=preserve,
            version=version,
            migrate=migrate,
        )

    @classmethod
    def resource(
        cls,
        module_name: str,
        name: str,
        factory: Callable[[], T | Awaitable[T]],
        close: Callable[[T], Any | Awaitable[Any]] | None = None,
        *,
        timeout: float = 10,
    ) -> RuntimeResource[T]:
        if timeout <= 0:
            raise ValueError("Resource timeout must be positive.")
        return cls.get_or_create(module_name).declare_resource(name, factory, close, timeout=timeout)

    @classmethod
    def cache_path(cls, module_name: str, name: str, version: int = 1) -> Path:
        return cls.get_or_create(module_name).declare_cache_path(name, version)

    @classmethod
    def cleanup(
        cls,
        module_name: str,
        callback: Callable[[], Any | Awaitable[Any]],
        *,
        name: str | None = None,
        timeout: float = 10,
    ) -> None:
        cls.get_or_create(module_name).declare_cleanup(callback, name=name, timeout=timeout)

    @classmethod
    def spawn(
        cls,
        module_name: str,
        awaitable: Awaitable[T],
        *,
        name: str | None = None,
        suppress_errors: tuple[type[BaseException], ...] = (),
    ) -> asyncio.Task[T]:
        return cls.get_or_create(module_name).spawn(awaitable, name=name, suppress_errors=suppress_errors)

    @classmethod
    def current(cls) -> ModuleRuntime:
        runtime = current_runtime.get()
        if runtime is None:
            raise RuntimeError("No module runtime is active in this context.")
        return runtime

    @classmethod
    @asynccontextmanager
    async def use(cls, module_name: str):
        token = current_runtime.set(cls.get_or_create(module_name))
        try:
            yield current_runtime.get()
        finally:
            current_runtime.reset(token)

    @classmethod
    def prepare_reload(cls, module_names: set[str]) -> dict[str, ModuleRuntime]:
        snapshot: dict[str, ModuleRuntime] = {}
        for module_name in module_names:
            runtime = cls._current.get(module_name)
            if runtime is None:
                continue
            snapshot[module_name] = runtime
            cls._staging[module_name] = runtime.next_generation()
        return snapshot

    @classmethod
    def abort_reload(
        cls,
        snapshot: dict[str, ModuleRuntime],
        module_names: set[str],
    ) -> None:
        for module_name in module_names:
            staged = cls._staging.pop(module_name, None)
            if staged is not None and staged is not snapshot.get(module_name):
                staged.cleanup_cache_paths()
            if module_name not in snapshot:
                runtime = cls._current.pop(module_name, None)
                if runtime is not None and runtime is not staged:
                    runtime.cleanup_cache_paths()

    @classmethod
    async def commit_reload(
        cls,
        snapshot: dict[str, ModuleRuntime],
        module_names: set[str],
        active_modules: set[str],
    ) -> None:
        for module_name in module_names:
            runtime = cls._staging.pop(module_name, None)
            if runtime is None:
                runtime = cls._current.get(module_name)
            if runtime is None:
                continue
            cls._current[module_name] = runtime
            if module_name in active_modules:
                runtime.activate()
            else:
                await runtime.stop("reload-disabled")
        for old_runtime in snapshot.values():
            await old_runtime.stop("reload")
        for module_name in module_names:
            old_runtime = snapshot.get(module_name)
            current = cls._current.get(module_name)
            if old_runtime is None or current is None:
                continue
            for name, current_path in current.cache_paths.items():
                old_path = old_runtime.cache_paths.get(name)
                if old_path is not None and old_path != current_path:
                    shutil.rmtree(old_path, ignore_errors=True)

    @classmethod
    def activate(cls, module_name: str) -> None:
        cls.get_or_create(module_name).activate()

    @classmethod
    async def suspend(cls, module_name: str) -> None:
        runtime = cls._current.get(module_name)
        if runtime is not None:
            await runtime.stop("disable")

    @classmethod
    async def shutdown(cls) -> None:
        for runtime in tuple(cls._current.values()):
            await runtime.stop("shutdown")
        cls._staging.clear()


__all__ = [
    "ModuleRuntime",
    "ModuleRuntimeManager",
    "RuntimeResource",
    "current_runtime",
]
