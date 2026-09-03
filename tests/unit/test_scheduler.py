"""计划任务系统单元测试 - 验证模块定时任务注册和执行。"""

import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from apscheduler.triggers.interval import IntervalTrigger as APSchedulerIntervalTrigger

import core.component as component
from core.config.base import CoreConfig
from core.database.models import ModuleStatus
from core.loader import ModulesManager
from core.scheduler import IntervalTrigger, Scheduler, SchedulerLifecycle
from core.tester import func_case, Tester
from core.tester.mock.scheduler import (
    get_scheduled_tasks,
    run_schedule_function,
)
from core.types import Module
from core.types.module.component_meta import ScheduleMeta


def _test_get_scheduled_tasks_has_structure():
    """get_scheduled_tasks: 每项应包含必要字段"""
    try:
        tasks = get_scheduled_tasks()
        if not tasks:
            return True  # 没有计划任务也算通过
        t = tasks[0]
        return (
            "module_name" in t and "function" in t and "function_name" in t and "trigger" in t and "trigger_type" in t
        )
    except Exception:
        return False


def _test_get_scheduled_tasks_filter_by_module():
    """get_scheduled_tasks: 按模块名过滤"""
    try:
        all_tasks = get_scheduled_tasks()
        if not all_tasks:
            return True
        first_module = all_tasks[0]["module_name"]
        filtered = get_scheduled_tasks(first_module)
        return all(t["module_name"] == first_module for t in filtered)
    except Exception:
        return False


def _test_schedule_meta_stored_in_module():
    """Module.schedule_list: 应正确存储 ScheduleMeta"""
    try:
        from core.types.module.component_meta import ScheduleMeta

        for name, mod in ModulesManager.modules.items():
            if mod.schedule_list and mod.schedule_list.set:
                for s in mod.schedule_list.set:
                    if not isinstance(s, ScheduleMeta):
                        return False
                    if not hasattr(s, "function"):
                        return False
                    if not hasattr(s, "trigger"):
                        return False
        return True
    except Exception:
        return False


def _test_schedule_triggers_are_valid():
    """计划任务: trigger 应为有效的 APScheduler 触发器类型"""
    try:
        from apscheduler.triggers.interval import IntervalTrigger
        from apscheduler.triggers.cron import CronTrigger
        from apscheduler.triggers.date import DateTrigger
        from apscheduler.triggers.combining import AndTrigger, OrTrigger

        valid_types = (IntervalTrigger, CronTrigger, DateTrigger, AndTrigger, OrTrigger)
        tasks = get_scheduled_tasks()
        for t in tasks:
            if not isinstance(t["trigger"], valid_types):
                return False
        return True
    except Exception:
        return False


def _test_schedule_functions_are_coroutine():
    """计划任务: 所有函数应为协程函数"""
    try:
        import asyncio

        tasks = get_scheduled_tasks()
        for t in tasks:
            if not asyncio.iscoroutinefunction(t["function"]):
                return False
        return True
    except Exception:
        return False


async def _test_run_schedule_function_with_noop():
    """run_schedule_function: 执行空函数应成功"""
    try:

        async def noop():
            pass

        result = await run_schedule_function(noop)
        return result["success"] is True and result["error"] is None
    except Exception:
        return False


async def _test_run_schedule_function_with_error():
    """run_schedule_function: 执行抛异常的函数应捕获错误"""
    try:

        async def failing():
            raise ValueError("test error")

        result = await run_schedule_function(failing)
        return result["success"] is False and "ValueError" in result["error"]
    except Exception:
        return False


async def _test_run_schedule_function_with_timeout():
    """run_schedule_function: 超时应被捕获"""
    try:

        async def slow():
            import asyncio

            await asyncio.sleep(100)

        result = await run_schedule_function(slow, timeout=0.1)
        return result["success"] is False and "Timeout" in result["error"]
    except Exception:
        return False


def _make_scheduled_module(module_name: str, function, loaded: bool = True) -> Module:
    module = Module.assign(module_name=module_name, alias=None, recommend_modules=None, developers=None)
    module._db_load = loaded
    module.schedule_list.add(ScheduleMeta(function=function, trigger=IntervalTrigger(hours=1)))
    return module


def _test_interval_trigger_applies_configured_multiplier():
    """IntervalTrigger 应将全局倍率应用于声明的间隔。"""
    with patch.object(CoreConfig, "schedule_interval_multiplier", 2.5):
        trigger = IntervalTrigger(minutes=2)
    return trigger.interval == timedelta(minutes=5) and trigger.interval_length == 300


def _test_interval_trigger_rejects_invalid_multiplier():
    """非正数倍率应在注册计划任务时立即失败。"""
    with patch.object(CoreConfig, "schedule_interval_multiplier", 0):
        try:
            IntervalTrigger(seconds=60)
        except ValueError:
            return True
    return False


def _test_registered_interval_schedules_use_configurable_trigger():
    """所有已注册的周期任务都应经过可配置的 IntervalTrigger。"""
    interval_triggers = [
        task["trigger"] for task in get_scheduled_tasks() if isinstance(task["trigger"], APSchedulerIntervalTrigger)
    ]
    return (
        bool(interval_triggers)
        and all(isinstance(trigger, IntervalTrigger) for trigger in interval_triggers)
        and component.IntervalTrigger is IntervalTrigger
    )


def _test_scheduler_reconcile_uses_stable_ids_and_explicit_limit():
    """模块 Job 使用稳定 ID，且显式传入正确的 max_instances 参数。"""
    module_name = "__test_scheduler_stable"

    async def first():
        pass

    async def second():
        pass

    module = _make_scheduled_module(module_name, first)
    module.schedule_list.add(ScheduleMeta(function=second, trigger=IntervalTrigger(hours=2)))
    try:
        SchedulerLifecycle.prepare()
        with patch.object(Scheduler, "add_job", wraps=Scheduler.add_job) as add_job:
            SchedulerLifecycle.reconcile_modules({module_name}, {module_name: module})
        ids = {SchedulerLifecycle.module_job_id(module_name, 0), SchedulerLifecycle.module_job_id(module_name, 1)}
        return (
            set(SchedulerLifecycle._module_job_ids.get(module_name, ())) == ids
            and all(Scheduler.get_job(job_id) is not None for job_id in ids)
            and add_job.call_count == 2
            and all(call.kwargs.get("max_instances") == 1 for call in add_job.call_args_list)
            and all("max_instance" not in call.kwargs for call in add_job.call_args_list)
        )
    finally:
        SchedulerLifecycle._remove_modules({module_name})


async def _test_module_load_unload_synchronizes_jobs():
    """全局 load/unload 应立即注册／删除模块 Job，无需重启 Server。"""
    module_name = "__test_scheduler_toggle"

    async def scheduled():
        pass

    module = _make_scheduled_module(module_name, scheduled, loaded=False)
    old_module = ModulesManager.modules.get(module_name)
    old_origin = ModulesManager.modules_origin.get(module_name)
    ModulesManager.modules[module_name] = module
    ModulesManager.modules_origin[module_name] = "modules.__test_scheduler_toggle"
    try:
        SchedulerLifecycle.prepare()
        with patch.object(ModuleStatus, "set_module_loaded", new=AsyncMock()):
            loaded = await ModulesManager.load_module(module_name)
            job_id = SchedulerLifecycle.module_job_id(module_name, 0)
            registered = Scheduler.get_job(job_id) is not None
            unloaded = await ModulesManager.unload_module(module_name)
        return loaded and registered and unloaded and Scheduler.get_job(job_id) is None and not module._db_load
    finally:
        SchedulerLifecycle._remove_modules({module_name})
        if old_module is None:
            ModulesManager.modules.pop(module_name, None)
            ModulesManager.modules_origin.pop(module_name, None)
        else:
            ModulesManager.modules[module_name] = old_module
            ModulesManager.modules_origin[module_name] = old_origin


async def _test_scheduler_maintenance_cancels_and_waits_running_job():
    """维护窗口不依赖真实时间：手动启动 wrapper，进入窗口时须等其 finally 完成。"""
    module_name = "__test_scheduler_maintenance"
    started = asyncio.Event()
    stopped = asyncio.Event()

    async def scheduled():
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    module = _make_scheduled_module(module_name, scheduled)
    SchedulerLifecycle.prepare()
    SchedulerLifecycle.reconcile_modules({module_name}, {module_name: module})
    job_id = SchedulerLifecycle.module_job_id(module_name, 0)
    job = Scheduler.get_job(job_id)
    task = asyncio.create_task(job.func())
    try:
        await asyncio.wait_for(started.wait(), timeout=1)
        async with SchedulerLifecycle.maintenance_window():
            waited_before_yield = stopped.is_set() and task.done()
            # 同一 Task 重入必须直接进入，不能在维护锁上自锁。
            async with SchedulerLifecycle.maintenance_window():
                nested = True
        return waited_before_yield and nested and SchedulerLifecycle._accepting_jobs
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        SchedulerLifecycle._remove_modules({module_name})


def _test_scheduler_snapshot_restores_old_function():
    """热重载失败回滚时，旧 Job 函数和 trigger 可由快照恢复。"""
    module_name = "__test_scheduler_restore"

    async def old_function():
        pass

    async def new_function():
        pass

    old_module = _make_scheduled_module(module_name, old_function)
    new_module = _make_scheduled_module(module_name, new_function)
    try:
        SchedulerLifecycle.prepare()
        SchedulerLifecycle.reconcile_modules({module_name}, {module_name: old_module})
        snapshot = SchedulerLifecycle.snapshot_modules({module_name})
        SchedulerLifecycle.reconcile_modules({module_name}, {module_name: new_module})
        replaced = (
            SchedulerLifecycle._job_specs[SchedulerLifecycle.module_job_id(module_name, 0)].function is new_function
        )
        SchedulerLifecycle.restore_modules(snapshot, {module_name})
        restored = (
            SchedulerLifecycle._job_specs[SchedulerLifecycle.module_job_id(module_name, 0)].function is old_function
        )
        return replaced and restored
    finally:
        SchedulerLifecycle._remove_modules({module_name})


async def _test_scheduler_shutdown_waits_and_reaches_real_shutdown_event():
    """shutdown 返回前须完成 Job 取消清理，并收到 APScheduler 的实际 shutdown event。"""
    module_name = "__test_scheduler_shutdown"
    started = asyncio.Event()
    stopped = asyncio.Event()

    async def scheduled():
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    module = _make_scheduled_module(module_name, scheduled)
    SchedulerLifecycle.prepare()
    SchedulerLifecycle.reconcile_modules({module_name}, {module_name: module})
    SchedulerLifecycle.start()
    job = Scheduler.get_job(SchedulerLifecycle.module_job_id(module_name, 0))
    task = asyncio.create_task(job.func())
    try:
        await asyncio.wait_for(started.wait(), timeout=1)
        await asyncio.wait_for(SchedulerLifecycle.shutdown(), timeout=1)
        return stopped.is_set() and task.done() and not Scheduler.running and not SchedulerLifecycle._job_specs
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        SchedulerLifecycle.prepare()


@func_case
async def test_scheduler_mock(tester: Tester):
    """计划任务 Mock 工具测试"""
    await tester.test(_test_get_scheduled_tasks_has_structure, "get_scheduled_tasks 字段结构")
    await tester.test(_test_get_scheduled_tasks_filter_by_module, "get_scheduled_tasks 按模块过滤")
    await tester.test(_test_schedule_meta_stored_in_module, "ScheduleMeta 存储正确")
    await tester.test(_test_schedule_triggers_are_valid, "触发器类型有效")
    await tester.test(_test_schedule_functions_are_coroutine, "函数为协程")
    await tester.test(_test_run_schedule_function_with_noop, "run_schedule_function 空函数")
    await tester.test(_test_run_schedule_function_with_error, "run_schedule_function 异常捕获")
    await tester.test(_test_run_schedule_function_with_timeout, "run_schedule_function 超时捕获")
    await tester.test(_test_interval_trigger_applies_configured_multiplier, "IntervalTrigger 应用间隔倍率")
    await tester.test(_test_interval_trigger_rejects_invalid_multiplier, "IntervalTrigger 拒绝无效倍率")
    await tester.test(
        _test_registered_interval_schedules_use_configurable_trigger,
        "全部周期计划任务使用可配置触发器",
    )
    await tester.test(_test_scheduler_reconcile_uses_stable_ids_and_explicit_limit, "Scheduler 稳定 ID 与并发上限")
    await tester.test(_test_module_load_unload_synchronizes_jobs, "模块全局启停同步 Scheduler")
    await tester.test(_test_scheduler_maintenance_cancels_and_waits_running_job, "Scheduler 维护窗口等待运行任务")
    await tester.test(_test_scheduler_snapshot_restores_old_function, "Scheduler Job 快照回滚")
    await tester.test(_test_scheduler_shutdown_waits_and_reaches_real_shutdown_event, "Scheduler 真正等待关闭")
    return tester
