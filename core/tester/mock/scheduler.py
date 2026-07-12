"""计划任务 Mock 工具 - 用于测试模块的定时任务注册和执行。

使用方式：
    1. 在测试中调用 get_scheduled_tasks() 获取所有已注册的计划任务
    2. 调用 run_schedule_function(func) 手动执行计划任务函数
    3. 调用 get_schedule_summary() 获取模块计划任务概览

计划任务注册流程：
    模块通过 @module.schedule(trigger) 装饰器注册 → ScheduleMeta 存入 Module.schedule_list.set
    Server 启动时遍历所有模块，调用 Scheduler.add_job() 注册到 APScheduler

Mock 方案：
    不启动 APScheduler，直接从 ModulesManager 中读取已注册的 ScheduleMeta，
    手动调用 function 来测试计划任务的逻辑。
"""

from __future__ import annotations

import asyncio
from typing import Callable

from core.loader import ModulesManager


def get_scheduled_tasks(module_name: str | None = None) -> list[dict]:
    """获取已注册的计划任务列表。

    :param module_name: 指定模块名，None 则返回所有模块的计划任务
    :returns: 计划任务信息列表，每项包含 module_name, function, trigger
    """
    tasks = []
    modules = ModulesManager.modules

    for name, mod in modules.items():
        if module_name and name != module_name:
            continue
        if not mod.schedule_list:
            continue
        for schedule in mod.schedule_list.set:
            tasks.append(
                {
                    "module_name": name,
                    "function": schedule.function,
                    "function_name": schedule.function.__name__
                    if hasattr(schedule.function, "__name__")
                    else str(schedule.function),
                    "trigger": schedule.trigger,
                    "trigger_type": type(schedule.trigger).__name__,
                }
            )

    return tasks


def get_schedule_summary() -> dict[str, list[str]]:
    """获取所有模块的计划任务概览。

    :returns: {module_name: [trigger_type, ...]} 字典
    """
    summary = {}
    tasks = get_scheduled_tasks()
    for t in tasks:
        name = t["module_name"]
        if name not in summary:
            summary[name] = []
        summary[name].append(t["trigger_type"])
    return summary


async def run_schedule_function(func: Callable, timeout: float = 30) -> dict:
    """手动执行一个计划任务函数。

    :param func: 计划任务函数
    :param timeout: 超时时间（秒）
    :returns: {"success": bool, "error": str | None, "elapsed": float}
    """
    import time

    start = time.time()
    try:
        await asyncio.wait_for(func(), timeout=timeout)
        return {"success": True, "error": None, "elapsed": time.time() - start}
    except asyncio.TimeoutError:
        return {"success": False, "error": "Timeout", "elapsed": time.time() - start}
    except Exception as e:
        return {"success": False, "error": f"{type(e).__name__}: {e}", "elapsed": time.time() - start}


async def run_all_schedules_for_module(module_name: str, timeout: float = 30) -> list[dict]:
    """执行指定模块的所有计划任务。

    :param module_name: 模块名
    :param timeout: 每个任务的超时时间
    :returns: 执行结果列表
    """
    tasks = get_scheduled_tasks(module_name)
    results = []
    for t in tasks:
        result = await run_schedule_function(t["function"], timeout=timeout)
        result["module_name"] = module_name
        result["function_name"] = t["function_name"]
        results.append(result)
    return results


__all__ = [
    "get_scheduled_tasks",
    "get_schedule_summary",
    "run_schedule_function",
    "run_all_schedules_for_module",
]
