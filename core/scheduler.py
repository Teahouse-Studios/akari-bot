"""基于 APScheduler 的计划任务与生命周期管理。"""

import asyncio
import inspect
from collections.abc import Callable, Iterable, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from functools import wraps
from typing import TYPE_CHECKING, Any

from apscheduler.events import EVENT_SCHEDULER_SHUTDOWN
from apscheduler.jobstores.base import JobLookupError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.schedulers.base import STATE_PAUSED, STATE_RUNNING, SchedulerAlreadyRunningError
from apscheduler.triggers.combining import AndTrigger, OrTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

if TYPE_CHECKING:
    from core.types import Module


Scheduler = AsyncIOScheduler()


@dataclass(frozen=True)
class ScheduledJobSpec:
    """可重建的计划任务描述。"""

    job_id: str
    function: Callable[..., Any]
    trigger: Any
    module_name: str | None = None


class SchedulerLifecycle:
    """统一管理模块计划任务、运行中实例和维护／关闭窗口。"""

    MODULE_JOB_PREFIX = "module:"
    CORE_JOB_PREFIX = "core:"
    _job_specs: dict[str, ScheduledJobSpec] = {}
    _module_job_ids: dict[str, set[str]] = {}
    _active_tasks: dict[asyncio.Task, str] = {}
    _launch_lock = asyncio.Lock()
    _maintenance_lock = asyncio.Lock()
    _maintenance_owner: asyncio.Task | None = None
    _accepting_jobs = True
    _shutting_down = False

    @classmethod
    def module_job_id(cls, module_name: str, index: int) -> str:
        """返回模块内第 ``index`` 个计划任务的稳定 APScheduler ID。"""
        return f"{cls.MODULE_JOB_PREFIX}{module_name}:{index}"

    @classmethod
    def _tracked_function(cls, spec: ScheduledJobSpec):
        @wraps(spec.function)
        async def runner():
            current = asyncio.current_task()
            if current is None:
                return None

            # maintenance 先关闭入口，再取得本锁作为提交屏障。已经 submit、但尚未
            # 开始业务函数的 coroutine 会在这里看到关闭状态并直接退出。
            async with cls._launch_lock:
                if not cls._accepting_jobs:
                    return None
                cls._active_tasks[current] = spec.job_id

            try:
                result = spec.function()
                if inspect.isawaitable(result):
                    return await result
                return result
            finally:
                cls._active_tasks.pop(current, None)

        return runner

    @classmethod
    def _install_spec(cls, spec: ScheduledJobSpec) -> None:
        Scheduler.add_job(
            func=cls._tracked_function(spec),
            trigger=spec.trigger,
            id=spec.job_id,
            name=spec.job_id,
            misfire_grace_time=30,
            max_instances=1,
            replace_existing=True,
        )
        cls._job_specs[spec.job_id] = spec
        if spec.module_name is not None:
            cls._module_job_ids.setdefault(spec.module_name, set()).add(spec.job_id)

    @classmethod
    def _remove_job(cls, job_id: str) -> None:
        try:
            Scheduler.remove_job(job_id)
        except JobLookupError:
            pass
        spec = cls._job_specs.pop(job_id, None)
        if spec and spec.module_name is not None:
            module_jobs = cls._module_job_ids.get(spec.module_name)
            if module_jobs is not None:
                module_jobs.discard(job_id)
                if not module_jobs:
                    cls._module_job_ids.pop(spec.module_name, None)

    @classmethod
    def _remove_modules(cls, module_names: Iterable[str]) -> None:
        for module_name in set(module_names):
            for job_id in tuple(cls._module_job_ids.get(module_name, ())):
                cls._remove_job(job_id)

    @classmethod
    def snapshot_modules(cls, module_names: Iterable[str]) -> dict[str, tuple[ScheduledJobSpec, ...]]:
        """保存指定模块当前的 Scheduler Job，以供 Loader 失败回滚。"""
        return {
            module_name: tuple(
                cls._job_specs[job_id]
                for job_id in sorted(cls._module_job_ids.get(module_name, ()))
                if job_id in cls._job_specs
            )
            for module_name in set(module_names)
        }

    @classmethod
    def restore_modules(
        cls,
        snapshot: Mapping[str, Iterable[ScheduledJobSpec]],
        module_names: Iterable[str] | None = None,
    ) -> None:
        """以快照替换指定模块的全部 Job。调用方须位于维护窗口内。"""
        names = set(module_names or snapshot)
        cls._remove_modules(names)
        for module_name in sorted(snapshot):
            for spec in snapshot[module_name]:
                cls._install_spec(spec)

    @classmethod
    def reconcile_modules(cls, module_names: Iterable[str], modules: Mapping[str, "Module"]) -> None:
        """让指定模块的 APScheduler Job 与当前 Module 注册表完全一致。"""
        names = set(module_names)
        old_jobs = cls.snapshot_modules(names)
        try:
            cls._remove_modules(names)
            for module_name in sorted(names):
                module = modules.get(module_name)
                if module is None or not module._db_load or not module.load:
                    continue
                for index, schedule in enumerate(module.schedule_list.set):
                    cls._install_spec(
                        ScheduledJobSpec(
                            job_id=cls.module_job_id(module_name, index),
                            function=schedule.function,
                            trigger=schedule.trigger,
                            module_name=module_name,
                        )
                    )
        except BaseException:
            cls.restore_modules(old_jobs, names)
            raise

    @classmethod
    def reconcile_all_modules(cls, modules: Mapping[str, "Module"]) -> None:
        """同步全部模块，并移除已经不存在的模块 Job。"""
        cls.reconcile_modules(set(modules) | set(cls._module_job_ids), modules)

    @classmethod
    def register_core_job(cls, job_name: str, function: Callable[..., Any], trigger: Any) -> str:
        """注册一个同样受维护／关闭窗口追踪的核心计划任务。"""
        job_id = f"{cls.CORE_JOB_PREFIX}{job_name}"
        old_spec = cls._job_specs.get(job_id)
        cls._remove_job(job_id)
        try:
            cls._install_spec(ScheduledJobSpec(job_id=job_id, function=function, trigger=trigger))
        except BaseException:
            if old_spec is not None:
                cls._install_spec(old_spec)
            raise
        return job_id

    @classmethod
    def prepare(cls) -> None:
        """为尚未启动的本轮 Server 生命周期开放 Job 入口。"""
        cls._shutting_down = False
        cls._accepting_jobs = True

    @classmethod
    def start(cls) -> None:
        """启动全局 Scheduler；重复调用保持幂等。"""
        cls.prepare()
        try:
            Scheduler.start()
        except SchedulerAlreadyRunningError:
            pass

    @classmethod
    def begin_shutdown(cls) -> None:
        """同步关闭新 Job 入口；实际取消和等待由 :meth:`shutdown` 完成。"""
        cls._shutting_down = True
        cls._accepting_jobs = False
        if Scheduler.state == STATE_RUNNING:
            Scheduler.pause()

    @classmethod
    def _selected_active_tasks(cls, module_names: set[str] | None) -> list[asyncio.Task]:
        current = asyncio.current_task()
        selected_ids = None
        if module_names is not None:
            selected_ids = {
                job_id for module_name in module_names for job_id in cls._module_job_ids.get(module_name, ())
            }
        return [
            task
            for task, job_id in tuple(cls._active_tasks.items())
            if task is not current and (selected_ids is None or job_id in selected_ids)
        ]

    @classmethod
    async def _cancel_active_tasks(cls, module_names: set[str] | None = None) -> None:
        tasks = cls._selected_active_tasks(module_names)
        for task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    @classmethod
    @asynccontextmanager
    async def maintenance_window(cls, module_names: Iterable[str] | None = None):
        """暂停新触发并取消、等待目标范围内正在运行的 Job。

        ``module_names=None`` 表示数据库级全局维护。窗口允许同一 Task 重入，
        Loader 外层覆盖 Python reload 时，``reload_db()`` 可再次进入而不死锁。
        """
        current = asyncio.current_task()
        if current is None:
            raise RuntimeError("Scheduler maintenance requires an asyncio task.")
        if current in cls._active_tasks:
            raise RuntimeError("A scheduled job cannot enter scheduler maintenance while it is running.")

        selected_modules = set(module_names) if module_names is not None else None
        if cls._maintenance_owner is current:
            await cls._cancel_active_tasks(selected_modules)
            yield
            return

        async with cls._maintenance_lock:
            cls._maintenance_owner = current
            old_accepting = cls._accepting_jobs
            old_state = Scheduler.state
            cls._accepting_jobs = False
            try:
                if old_state == STATE_RUNNING:
                    Scheduler.pause()
                # 与所有已经进入／正在等待 wrapper 启动临界区的任务建立屏障。
                async with cls._launch_lock:
                    pass
                await cls._cancel_active_tasks(selected_modules)
                yield
            finally:
                cls._maintenance_owner = None
                if not cls._shutting_down:
                    cls._accepting_jobs = old_accepting
                    if old_state == STATE_RUNNING and Scheduler.state == STATE_PAUSED:
                        Scheduler.resume()

    @classmethod
    async def shutdown(cls) -> None:
        """真正停止 Scheduler，并等待所有运行中业务 coroutine 完成取消。"""
        current = asyncio.current_task()
        if current in cls._active_tasks:
            raise RuntimeError("A scheduled job cannot shut down its own scheduler.")

        async with cls._maintenance_lock:
            cls.begin_shutdown()
            async with cls._launch_lock:
                pass
            await cls._cancel_active_tasks()

            if Scheduler.running:
                stopped = asyncio.Event()

                def on_shutdown(_event):
                    stopped.set()

                Scheduler.add_listener(on_shutdown, EVENT_SCHEDULER_SHUTDOWN)
                try:
                    # AsyncIOScheduler.shutdown() 只把真正的关闭回调排进事件循环；
                    # 等待 shutdown event 才能保证回调已经执行，而非仅“调用过”。
                    Scheduler.shutdown(wait=False)
                    await stopped.wait()
                finally:
                    Scheduler.remove_listener(on_shutdown)
            else:
                # 初始化中途失败时 Scheduler 尚未 start，但可能已有 pending jobs。
                Scheduler.remove_all_jobs()

            cls._active_tasks.clear()
            cls._job_specs.clear()
            cls._module_job_ids.clear()


__all__ = [
    "Scheduler",
    "SchedulerLifecycle",
    "ScheduledJobSpec",
    "AndTrigger",
    "OrTrigger",
    "CronTrigger",
    "DateTrigger",
    "IntervalTrigger",
]
