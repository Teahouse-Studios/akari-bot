"""测试进程内的任务回收。"""

import asyncio

from core.tester.timing import TIME_SCALE

# 取消后的收尾有界：后台任务可能在自己的 CancelledError 处理里继续等待，
# 无限等待会让卡死的用例拖住整个进程。
CANCEL_TIMEOUT = 1.0 * TIME_SCALE


def consume_task_result(task: asyncio.Task) -> None:
    if task.cancelled():
        return
    try:
        task.exception()
    except asyncio.CancelledError:
        pass


async def cancel_task(task: asyncio.Task) -> bool:
    """取消单个任务，返回它是否在时限内完成收尾。"""
    if task.done():
        await asyncio.gather(task, return_exceptions=True)
        return True
    task.cancel()
    done, _ = await asyncio.wait((task,), timeout=CANCEL_TIMEOUT)
    if task not in done:
        task.cancel()
        task.add_done_callback(consume_task_result)
        return False
    await asyncio.gather(task, return_exceptions=True)
    return True


async def current_tasks() -> set[asyncio.Task]:
    """当前未完成的任务集合。"""
    return {task for task in asyncio.all_tasks() if not task.done()}


async def cancel_orphan_tasks(baseline: set[asyncio.Task] | None = None) -> bool:
    """取消 baseline 之外的任务，返回它们是否全部在时限内完成收尾。"""
    current = asyncio.current_task()
    tasks = [
        task
        for task in asyncio.all_tasks()
        if task is not current
        and not task.done()
        and not task.get_name().startswith("function-test-progress:")
        and (baseline is None or task not in baseline)
    ]
    if not tasks:
        return True
    completed = await asyncio.gather(*(cancel_task(task) for task in tasks))
    return all(completed)


__all__ = ["CANCEL_TIMEOUT", "cancel_orphan_tasks", "cancel_task", "consume_task_result", "current_tasks"]
