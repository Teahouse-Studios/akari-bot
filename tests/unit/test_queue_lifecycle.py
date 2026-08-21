"""core.queue.base 单元测试 - 队列任务清理与取消恢复。"""

import asyncio
from datetime import datetime, timedelta, UTC
from unittest.mock import AsyncMock, patch

from core.database.models import JobQueuesTable
from core.queue.base import JobQueueBase
from core.queue.server import JobQueueServer
from core.exports import exports
from core.tester import func_case, Tester


async def _test_cleanup_keeps_active_tasks():
    """测试定时清理 - 只删除过期终态任务，不删除仍可执行的活动任务。"""
    old = datetime.now(UTC) - timedelta(minutes=90)
    task_ids = {}
    for status in ("pending", "processing", "done", "failed", "timeout"):
        task_id = await JobQueuesTable.add_task("QUEUE-AUDIT", f"cleanup-{status}", {})
        await JobQueuesTable.filter(task_id=task_id).update(status=status, timestamp=old)
        task_ids[status] = task_id

    await JobQueuesTable.clear_task(time=3600)

    remaining = {
        str(task_id)
        for task_id in await JobQueuesTable.filter(task_id__in=list(task_ids.values())).values_list(
            "task_id", flat=True
        )
    }
    return (
        str(task_ids["pending"]) in remaining
        and str(task_ids["processing"]) in remaining
        and all(str(task_ids[status]) not in remaining for status in ("done", "failed", "timeout"))
    )


async def _test_cleanup_marks_stale_active_timeout():
    """测试定时清理 - 超过执行上限的活动任务先标记 timeout，供等待方读取。"""
    old = datetime.now(UTC) - timedelta(hours=3)
    task_ids = []
    for status in ("pending", "processing"):
        task_id = await JobQueuesTable.add_task("QUEUE-AUDIT", f"stale-{status}", {})
        await JobQueuesTable.filter(task_id=task_id).update(status=status, timestamp=old)
        task_ids.append(task_id)

    await JobQueuesTable.clear_task(time=3600)
    rows = await JobQueuesTable.filter(task_id__in=task_ids)
    return len(rows) == 2 and all(row.status == "timeout" and row.result == {} for row in rows)


async def _test_cancelled_processing_becomes_failed():
    """测试处理取消 - 任务进入 failed 终态，避免永久卡在 processing 或重复执行副作用。"""

    class AuditQueue(JobQueueBase):
        queue_actions = {}

    started = asyncio.Event()
    never = asyncio.Event()

    @AuditQueue.action("cancel-audit")
    async def _handler(tsk, args):
        started.set()
        await never.wait()
        return {"success": True}

    task_id = await JobQueuesTable.add_task("QUEUE-AUDIT", "cancel-audit", {})
    row = await JobQueuesTable.get(task_id=task_id)
    await row.set_status("processing")

    processing = asyncio.create_task(AuditQueue._process_task(row))
    await asyncio.wait_for(started.wait(), timeout=1)
    processing.cancel()
    try:
        await processing
    except asyncio.CancelledError:
        pass

    refreshed = await JobQueuesTable.get(task_id=task_id)
    return refreshed.status == "failed" and refreshed.result == {}


async def _test_completed_task_persists_for_waiter():
    """测试处理完成 - 结果行保留到定时清理，等待方短暂离线后仍能读取。"""

    class AuditQueue(JobQueueBase):
        queue_actions = {}

    @AuditQueue.action("done-audit")
    async def _handler(tsk, args):
        return {"value": 1}

    task_id = await JobQueuesTable.add_task("QUEUE-AUDIT", "done-audit", {})
    row = await JobQueuesTable.get(task_id=task_id)
    await row.set_status("processing")

    # 旧实现会在完成后 sleep(5) 再删除结果行；替换 sleep 使失败能够立即复现。
    with patch("core.queue.base.asyncio.sleep", new=AsyncMock()):
        await AuditQueue._process_task(row)

    refreshed = await JobQueuesTable.get_or_none(task_id=task_id)
    return refreshed is not None and refreshed.status == "done" and refreshed.result == {"value": 1}


async def _test_concurrent_consumers_claim_once():
    """测试任务领取 - 两个消费者读到同一 pending 快照时仍只执行一次。"""

    class AuditQueue(JobQueueBase):
        name = "QUEUE-AUDIT-INTERNAL"
        queue_actions = {}

    handler_calls = 0

    @AuditQueue.action("claim-audit")
    async def _handler(tsk, args):
        nonlocal handler_calls
        handler_calls += 1
        return {"calls": handler_calls}

    task_id = await JobQueuesTable.add_task("QUEUE-AUDIT-CLAIM", "claim-audit", {})
    readers = 0
    both_read = asyncio.Event()

    async def _get_same_pending_snapshot(target_clients):
        nonlocal readers
        row = await JobQueuesTable.get(task_id=task_id)
        readers += 1
        if readers == 2:
            both_read.set()
        await both_read.wait()
        return [row]

    scheduled = []

    def _capture_task(coro):
        task = asyncio.get_running_loop().create_task(coro)
        scheduled.append(task)
        return task

    with (
        patch.object(JobQueuesTable, "get_all", side_effect=_get_same_pending_snapshot),
        patch("core.queue.base.asyncio.create_task", side_effect=_capture_task),
    ):
        await asyncio.gather(
            AuditQueue._check_queue("QUEUE-AUDIT-CLAIM"),
            AuditQueue._check_queue("QUEUE-AUDIT-CLAIM"),
        )

    await asyncio.gather(*scheduled)
    refreshed = await JobQueuesTable.get(task_id=task_id)
    return len(scheduled) == 1 and handler_calls == 1 and refreshed.status == "done"


async def _test_trigger_hook_result_is_not_overwritten():
    """trigger_hook 应由统一处理流程写回一次，不能先写真实值又被空字典覆盖。"""
    task_id = await JobQueuesTable.add_task("QUEUE-AUDIT", "trigger_hook", {})
    row = await JobQueuesTable.get(task_id=task_id)
    await row.set_status("processing")
    expected = {"hook": "value"}

    with patch.object(exports["Bot"].Hook, "trigger", new=AsyncMock(return_value=expected)):
        await JobQueueServer._process_task(row)

    refreshed = await JobQueuesTable.get(task_id=task_id)
    return refreshed.status == "done" and refreshed.result == {"result": expected}


@func_case
async def test_queue_lifecycle(tester: Tester):
    """core.queue.base: 队列生命周期测试。"""
    await tester.test(_test_cleanup_keeps_active_tasks, "定时清理保留活动任务测试")
    await tester.test(_test_cleanup_marks_stale_active_timeout, "超时活动任务进入 timeout 测试")
    await tester.test(_test_cancelled_processing_becomes_failed, "处理取消进入 failed 测试")
    await tester.test(_test_completed_task_persists_for_waiter, "完成结果保留到定时清理测试")
    await tester.test(_test_concurrent_consumers_claim_once, "并发消费者只领取一次测试")
    await tester.test(_test_trigger_hook_result_is_not_overwritten, "trigger_hook 返回值不被覆盖测试")
    return tester
