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

from core.constants.info import Info
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


class strict_http:
    """在上下文内让未录制的 HTTP 请求立即失败。

    mock 未命中时默认回落到真实网络，且带有重试与超时（默认 3 次 × 20 秒）。
    定时任务往往串联多个外部请求，任一未录制的 URL 都会让用例拖上一分钟以上，
    并把测试结果与线上状态绑定。此上下文将这种回落改为即时失败。
    """

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self._previous = False

    def __enter__(self):
        self._previous = Info.http_mock_strict
        Info.http_mock_strict = self.enabled
        return self

    def __exit__(self, *exc_info):
        Info.http_mock_strict = self._previous
        return False


def reset_startup_mute(module_path: str) -> bool:
    """关闭模块的首轮静默开关。

    多个 RSS 模块以模块级 ``startup_mute`` 抑制启动后的第一轮推送，
    以免机器人重启时重复刷屏。测试需要立刻观察到推送行为，故直接置为关闭。

    :param module_path: 模块的导入路径，如 ``modules.mcv_rss``。
    :return: 是否确实存在并重置了该开关。
    """
    import importlib

    try:
        mod = importlib.import_module(module_path)
    except ImportError:
        return False

    current = getattr(mod, "startup_mute", None)
    if current is None:
        return False
    if isinstance(current, list):
        setattr(mod, "startup_mute", [False] * len(current))
    else:
        setattr(mod, "startup_mute", False)
    return True


async def force_run_schedule(
    module_name: str,
    module_path: str | None = None,
    stored_keys: tuple[str, ...] = (),
    timeout: float = 30,
) -> list[dict]:
    """无视内部闸门，立即触发指定模块的全部定时任务。

    定时任务在生产环境按触发器择时运行，并普遍带有「首轮静默」与「已推送去重」
    两类闸门。测试直接调用函数即可绕过触发器，但仍需清除上述闸门，否则函数虽然
    执行却不会产生任何可观察的行为。

    :param module_name: 注册的模块名，用于取出其定时任务。
    :param module_path: 模块导入路径，提供时会重置其 startup_mute。
    :param stored_keys: 需要清空的持久化去重列表键名。
    :param timeout: 单个任务的超时时间（秒）。
    :return: 每个任务的执行结果列表。
    """
    from core.builtins.bot import Bot
    from core.utils.storedata import update_stored_list

    if module_path:
        reset_startup_mute(module_path)
    for key in stored_keys:
        await update_stored_list(Bot.Info.client_name, key, [])

    return await run_all_schedules_for_module(module_name, timeout=timeout)


def get_module_hooks(module_name: str | None = None) -> dict[str, Callable]:
    """获取已注册的具名钩子。

    钩子以 ``{模块名}.{钩子名}`` 为键注册在 ``ModulesManager.modules_hooks``，
    生产环境经由 JobQueue 的 trigger_hook 动作分发。

    :param module_name: 指定模块名，None 则返回全部钩子。
    :returns: {钩子全名: 钩子函数} 字典。
    """
    hooks = ModulesManager.modules_hooks
    if module_name is None:
        return dict(hooks)
    return {name: fn for name, fn in hooks.items() if name.split(".")[0] == module_name}


async def run_hook(hook_name: str, args: dict | None = None, session_info=None, timeout: float = 30) -> dict:
    """按名手动触发一个具名钩子。

    以与生产环境一致的方式构造 ``ModuleHookContext`` 并调用钩子函数，
    从而覆盖钩子内部逻辑，而不仅仅是它的注册状态。

    :param hook_name: 钩子全名，形如 ``wikilog.keepalive``。
    :param args: 传递给钩子的参数字典。
    :param session_info: 触发钩子的会话，部分钩子依赖它取得场景信息。
    :param timeout: 超时时间（秒）。
    :returns: {"success": bool, "error": str | None, "result": Any}
    """
    from core.builtins.session.info import ModuleHookContext

    hooks = ModulesManager.modules_hooks
    if hook_name not in hooks:
        return {"success": False, "error": f"Unknown hook: {hook_name}", "result": None}

    ctx = ModuleHookContext(args or {}, session_info=session_info)
    try:
        result = await asyncio.wait_for(hooks[hook_name](ctx), timeout=timeout)
        return {"success": True, "error": None, "result": result}
    except asyncio.TimeoutError:
        return {"success": False, "error": "Timeout", "result": None}
    except Exception as e:
        return {"success": False, "error": f"{type(e).__name__}: {e}", "result": None}


__all__ = [
    "get_scheduled_tasks",
    "get_schedule_summary",
    "run_schedule_function",
    "run_all_schedules_for_module",
    "get_module_hooks",
    "run_hook",
    "force_run_schedule",
    "reset_startup_mute",
    "strict_http",
]
