"""core.queue.base 单元测试 - 队列任务清理与取消恢复。"""

import asyncio
from dataclasses import replace
from datetime import datetime, timedelta, UTC
from unittest.mock import AsyncMock, patch

from core.database.models import JobQueuesTable
from core.queue.base import JobQueueBase
from core.queue.codec import decode
from core.queue.contracts import ServerAPI
from core.queue.server import JobQueueServer
from core.queue.transport import PROTOCOL_VERSION, RpcResponse
from core.exports import exports
from core.tester import func_case, Tester


class QueueAuditRuntime(JobQueueBase):
    """为直接传输测试提供显式数据库后端。"""


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
    """测试定时清理 - 等待型活动任务标记 timeout，免回包活动任务直接删除。"""
    old = datetime.now(UTC) - timedelta(hours=3)
    task_ids = []
    for status in ("pending", "processing"):
        task_id = await JobQueuesTable.add_task("QUEUE-AUDIT", f"stale-{status}", {})
        await JobQueuesTable.filter(task_id=task_id).update(status=status, timestamp=old)
        task_ids.append(task_id)
    fire_and_forget_id = await JobQueuesTable.add_task("QUEUE-AUDIT", "stale-submit", {})
    await JobQueuesTable.filter(task_id=fire_and_forget_id).update(
        status="processing", timestamp=old, expects_response=False
    )

    await JobQueuesTable.clear_task(time=3600)
    rows = await JobQueuesTable.filter(task_id__in=task_ids)
    fire_and_forget = await JobQueuesTable.get_or_none(task_id=fire_and_forget_id)
    return (
        len(rows) == 2 and all(row.status == "timeout" and row.result == {} for row in rows) and fire_and_forget is None
    )


async def _test_cancelled_fire_and_forget_task_is_deleted():
    """测试处理取消 - 无需回包的任务直接删除，且不会恢复为 pending 后重试。"""

    class AuditQueue(JobQueueBase):
        pass

    started = asyncio.Event()
    never = asyncio.Event()

    @AuditQueue.register("cancel-audit")
    async def _handler(args):
        started.set()
        await never.wait()
        return {"success": True}

    task_id = await AuditQueue.submit("QUEUE-CANCEL-AUDIT", "cancel-audit", {})
    (request,) = await AuditQueue.transport.receive(["QUEUE-CANCEL-AUDIT"])

    processing = asyncio.create_task(AuditQueue._process_task(request))
    await asyncio.wait_for(started.wait(), timeout=1)
    processing.cancel()
    try:
        await processing
    except asyncio.CancelledError:
        pass

    refreshed = await JobQueuesTable.get_or_none(task_id=task_id)
    pending = await AuditQueue.transport.receive(["QUEUE-CANCEL-AUDIT"])
    return refreshed is None and not pending


async def _test_completed_task_is_deleted_after_response_consumption():
    """测试处理完成 - 等待型结果保留至调用方读取，并在读取后立即删除。"""

    class AuditQueue(JobQueueBase):
        pass

    @AuditQueue.register("done-audit")
    async def _handler(args):
        return {"value": 1}

    request = AuditQueue._request("QUEUE-DONE-AUDIT", "done-audit", {}, timeout=2)
    await AuditQueue.transport.send(request)
    (received,) = await AuditQueue.transport.receive(["QUEUE-DONE-AUDIT"])
    await AuditQueue._process_task(received)

    stored = await JobQueuesTable.get_or_none(task_id=request.task_id)
    responses = await AuditQueue.transport.consume_responses([request.task_id])
    deleted = await JobQueuesTable.get_or_none(task_id=request.task_id)
    return (
        stored is not None
        and stored.status == "done"
        and stored.result["value"] == {"value": 1}
        and len(responses) == 1
        and responses[0].envelope["value"] == {"value": 1}
        and deleted is None
    )


async def _test_completed_fire_and_forget_task_is_deleted():
    """测试处理完成 - 无需回包的任务不写入终态结果。"""

    class AuditQueue(JobQueueBase):
        pass

    @AuditQueue.register("submit-audit")
    async def _handler(args):
        return {"value": args["value"] + 1}

    task_id = await AuditQueue.submit("QUEUE-SUBMIT-AUDIT", "submit-audit", {"value": 1})
    (request,) = await AuditQueue.transport.receive(["QUEUE-SUBMIT-AUDIT"])
    await AuditQueue._process_task(request)
    return await JobQueuesTable.get_or_none(task_id=task_id) is None


async def _test_concurrent_consumers_claim_once():
    """测试任务领取 - 两个消费者读到同一 pending 快照时仍只执行一次。"""

    class AuditQueue(JobQueueBase):
        name = "QUEUE-AUDIT-INTERNAL"

    handler_calls = 0

    @AuditQueue.register("claim-audit")
    async def _handler(args):
        nonlocal handler_calls
        handler_calls += 1
        return {"calls": handler_calls}

    task_id = await AuditQueue.submit("QUEUE-AUDIT-CLAIM", "claim-audit", {})
    readers = 0
    both_read = asyncio.Event()
    original_get_all = JobQueuesTable.get_all

    async def _get_same_pending_snapshot(target_clients, limit=None):
        # 补丁作用于进程级的 JobQueuesTable，同一事件循环中其它 Peer 的轮询器也会命中。
        # 非本测试目标须原样放行，否则外部轮询器会占用会合名额，使本测试的协程永久等待。
        if "QUEUE-AUDIT-CLAIM" not in target_clients:
            return await original_get_all(target_clients, limit=limit)
        nonlocal readers
        try:
            row = await JobQueuesTable.get(task_id=task_id)
        finally:
            # 读取失败亦须放行对端：否则异常将表现为无进展挂起，掩盖真实原因。
            readers += 1
            if readers >= 2:
                both_read.set()
        await asyncio.wait_for(both_read.wait(), timeout=10)
        return [row]

    scheduled = []

    def _capture_task(coro, **kwargs):
        task = asyncio.get_running_loop().create_task(coro, **kwargs)
        # 同上：只登记本任务派发的处理协程，避免等待其它轮询器的在途任务。
        if str(kwargs.get("name", "")).endswith(str(task_id)):
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
    refreshed = await JobQueuesTable.get_or_none(task_id=task_id)
    pending = await AuditQueue.transport.receive(["QUEUE-AUDIT-CLAIM"])
    return len(scheduled) == 1 and handler_calls == 1 and refreshed is None and not pending


async def _test_database_claim_batch_is_bounded():
    """数据库积压不得在单轮轮询中触发无上限的领取写入。"""
    target = "QUEUE-BOUNDED-CLAIM"
    task_ids = [await JobQueuesTable.add_task(target, "bounded", {"index": index}) for index in range(3)]
    try:
        with patch.object(type(QueueAuditRuntime.transport), "CLAIM_BATCH_SIZE", 2):
            received = await QueueAuditRuntime.transport.receive([target], QueueAuditRuntime.name)
        pending = await JobQueuesTable.filter(task_id__in=task_ids, status="pending").count()
        processing = await JobQueuesTable.filter(task_id__in=task_ids, status="processing").count()
        return len(received) == 2 and pending == 1 and processing == 2
    finally:
        await JobQueuesTable.filter(task_id__in=task_ids).delete()


async def _test_trigger_hook_result_is_not_overwritten():
    """trigger_hook 应由统一处理流程写回一次，不能先写真实值又被空字典覆盖。"""
    request = QueueAuditRuntime._request(
        "QUEUE-HOOK-AUDIT",
        ServerAPI.trigger_hook.name,
        ServerAPI.trigger_hook.encode_arguments("example"),
        timeout=2,
    )
    await QueueAuditRuntime.transport.send(request)
    (received,) = await JobQueueServer.transport.receive(["QUEUE-HOOK-AUDIT"])
    expected = {"hook": "value"}

    with patch.object(exports["Bot"].Hook, "trigger", new=AsyncMock(return_value=expected)):
        await JobQueueServer._process_task(received)

    (response,) = await QueueAuditRuntime.transport.consume_responses([request.task_id])
    refreshed = await JobQueuesTable.get_or_none(task_id=request.task_id)
    return (
        refreshed is None
        and response.status == "done"
        and decode(response.envelope["value"], ServerAPI.trigger_hook.result_type) == expected
    )


async def _test_fire_and_forget_finish_only_deletes_claimed_task():
    """免回包完成操作必须限定 processing，避免异常调用删除尚未领取的任务。"""
    task_id = str(await JobQueuesTable.add_task("QUEUE-FINISH-GUARD", "guard", {}))
    await JobQueuesTable.filter(task_id=task_id).update(expects_response=False)
    request = QueueAuditRuntime._request("QUEUE-FINISH-GUARD", "guard", {}, timeout=2, expects_response=False)
    request = replace(request, task_id=task_id)
    await QueueAuditRuntime.transport.respond(
        request,
        RpcResponse(task_id, "done", {"rpc": PROTOCOL_VERSION, "value": None}),
    )
    row = await JobQueuesTable.get_or_none(task_id=task_id)
    await JobQueuesTable.filter(task_id=task_id).delete()
    return row is not None and row.status == "pending"


@func_case
async def test_queue_lifecycle(tester: Tester):
    """core.queue.base: 队列生命周期测试。"""
    await tester.test(_test_cleanup_keeps_active_tasks, "定时清理保留活动任务测试")
    await tester.test(_test_cleanup_marks_stale_active_timeout, "超时活动任务进入 timeout 测试")
    await tester.test(_test_cancelled_fire_and_forget_task_is_deleted, "取消的免回包任务及时删除测试")
    await tester.test(_test_completed_task_is_deleted_after_response_consumption, "等待型结果消费后删除测试")
    await tester.test(_test_completed_fire_and_forget_task_is_deleted, "完成的免回包任务及时删除测试")
    await tester.test(_test_concurrent_consumers_claim_once, "并发消费者只领取一次测试")
    await tester.test(_test_database_claim_batch_is_bounded, "数据库单轮领取数量有上限")
    await tester.test(_test_trigger_hook_result_is_not_overwritten, "trigger_hook 返回值不被覆盖测试")
    await tester.test(_test_fire_and_forget_finish_only_deletes_claimed_task, "免回包完成仅删除已领取任务")
    return tester
