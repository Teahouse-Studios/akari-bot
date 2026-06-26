"""计划任务系统单元测试 - 验证模块定时任务注册和执行。"""

from core.loader import ModulesManager
from core.tester import func_case, Tester
from core.tester.mock.scheduler import (
    get_scheduled_tasks,
    get_schedule_summary,
    run_schedule_function,
)


def _test_get_scheduled_tasks_returns_list():
    """get_scheduled_tasks: 应返回列表"""
    try:
        tasks = get_scheduled_tasks()
        return isinstance(tasks, list)
    except Exception:
        return False


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


def _test_get_schedule_summary_returns_dict():
    """get_schedule_summary: 应返回字典"""
    try:
        summary = get_schedule_summary()
        return isinstance(summary, dict)
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


@func_case
async def test_scheduler_mock(tester: Tester):
    """计划任务 Mock 工具测试"""
    await tester.test(_test_get_scheduled_tasks_returns_list, "get_scheduled_tasks 返回列表")
    await tester.test(_test_get_scheduled_tasks_has_structure, "get_scheduled_tasks 字段结构")
    await tester.test(_test_get_schedule_summary_returns_dict, "get_schedule_summary 返回字典")
    await tester.test(_test_get_scheduled_tasks_filter_by_module, "get_scheduled_tasks 按模块过滤")
    await tester.test(_test_schedule_meta_stored_in_module, "ScheduleMeta 存储正确")
    await tester.test(_test_schedule_triggers_are_valid, "触发器类型有效")
    await tester.test(_test_schedule_functions_are_coroutine, "函数为协程")
    await tester.test(_test_run_schedule_function_with_noop, "run_schedule_function 空函数")
    await tester.test(_test_run_schedule_function_with_error, "run_schedule_function 异常捕获")
    await tester.test(_test_run_schedule_function_with_timeout, "run_schedule_function 超时捕获")
    return tester
