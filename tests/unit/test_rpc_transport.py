"""RPC runtime tests over real database rows, including lifecycle boundaries."""

import asyncio
import time
from contextlib import asynccontextmanager
from dataclasses import replace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from tortoise.queryset import QuerySet

from core.database.models import JobQueuesTable
from core.logger import Logger
from core.queue.base import current_peer, JobQueueBase
from core.queue.errors import (
    RpcCancelledError,
    RpcMethodNotFoundError,
    RpcProtocolError,
    RpcRemoteError,
    RpcTimeoutError,
    RpcUnavailableError,
)
from core.queue.transport import PROTOCOL_VERSION, RpcRequest, RpcResponse
from core.tester import func_case, Tester


RPC_TEST_TIMEOUT = 10


@asynccontextmanager
async def _peers():
    class Caller(JobQueueBase):
        name = f"RPC-TEST-CALLER-{uuid4()}"
        POLL_INTERVAL_SECONDS = 0.005

    class Receiver(JobQueueBase):
        name = f"RPC-TEST-RECEIVER-{uuid4()}"
        POLL_INTERVAL_SECONDS = 0.005

    pollers = [asyncio.create_task(peer.check_job_queue(peer.name)) for peer in (Caller, Receiver)]
    try:
        yield Caller, Receiver
    finally:
        await asyncio.gather(*(peer.begin_shutdown() for peer in (Caller, Receiver)))
        await asyncio.gather(*(peer.cancel_process_tasks() for peer in (Caller, Receiver)))
        for task in pollers:
            task.cancel()
        await asyncio.gather(*pollers, return_exceptions=True)
        await JobQueuesTable.filter(target_peer__in=[Caller.name, Receiver.name]).delete()


async def _wait_status(task_id, status):
    async with asyncio.timeout(RPC_TEST_TIMEOUT):
        while True:
            row = await JobQueuesTable.get(task_id=task_id)
            if row.status == status:
                return row
            await asyncio.sleep(0.005)


async def _test_roundtrip_preserves_json_and_registry_isolation():
    async with _peers() as (caller, receiver):

        @receiver.register("echo")
        async def echo(payload):
            assert current_peer.get() is receiver
            return payload

        values = [None, False, True, 0, "", [], {}, [False, {"value": None}], {"x": [1, "二"]}]
        results = await asyncio.gather(
            *(caller.call(receiver.name, "echo", value, timeout=RPC_TEST_TIMEOUT) for value in values)
        )
        assert results == values
        assert "echo" not in caller.handlers
        assert caller._pending is not receiver._pending
        assert caller._process_tasks is not receiver._process_tasks
        assert caller.pause_event is not receiver.pause_event
        assert current_peer.get() is None
        assert not caller._pending
        assert not await JobQueuesTable.filter(source_peer_id=caller.name, action="echo").exists()
    return True


async def _test_bidirectional_nested_calls():
    async with _peers() as (caller, receiver):

        @caller.register("callback")
        async def callback(payload):
            return {"value": payload["value"] + 1}

        @receiver.register("outer")
        async def outer(payload):
            return await current_peer.get().call(caller.name, "callback", payload, timeout=RPC_TEST_TIMEOUT)

        result = await asyncio.gather(
            *(caller.call(receiver.name, "outer", {"value": n}, timeout=RPC_TEST_TIMEOUT) for n in range(8))
        )
        assert result == [{"value": n + 1} for n in range(8)]
    return True


async def _test_remote_errors_and_invalid_method_are_distinct():
    async with _peers() as (caller, receiver):

        @receiver.register("broken")
        async def broken(payload):
            raise ValueError("deliberate handler failure")

        @receiver.register("application_timeout")
        async def application_timeout(payload):
            raise TimeoutError("upstream timeout")

        report = AsyncMock()
        with patch.object(receiver, "report_error", report):
            try:
                await caller.call(receiver.name, "broken", {}, timeout=RPC_TEST_TIMEOUT)
                return False
            except RpcRemoteError as exc:
                assert exc.remote_type == "ValueError"
                assert exc.method == "broken" and exc.target == receiver.name and exc.task_id
                assert str(exc) == "deliberate handler failure"
            try:
                await caller.call(receiver.name, "missing", {}, timeout=RPC_TEST_TIMEOUT)
                return False
            except RpcMethodNotFoundError:
                pass
            try:
                await caller.call(receiver.name, "application_timeout", {}, timeout=RPC_TEST_TIMEOUT)
                return False
            except RpcRemoteError as exc:
                assert exc.remote_type == "TimeoutError" and not isinstance(exc, RpcTimeoutError)
        assert report.await_count == 2
        assert not caller._pending
    return True


async def _test_local_cancellation_does_not_cancel_or_retry_remote_effect():
    async with _peers() as (caller, receiver):
        started, proceed = asyncio.Event(), asyncio.Event()
        calls = 0

        @receiver.register("effect")
        async def effect(payload):
            nonlocal calls
            calls += 1
            started.set()
            await proceed.wait()
            return "effect-completed"

        task = asyncio.create_task(caller.call(receiver.name, "effect", None, timeout=RPC_TEST_TIMEOUT))
        await asyncio.wait_for(started.wait(), RPC_TEST_TIMEOUT)
        (task_id,) = caller._pending
        task.cancel()
        (result,) = await asyncio.gather(task, return_exceptions=True)
        assert isinstance(result, asyncio.CancelledError)
        assert not caller._pending
        assert await JobQueuesTable.get_or_none(task_id=task_id) is None
        proceed.set()
        await receiver.wait_process_tasks()
        assert await JobQueuesTable.get_or_none(task_id=task_id) is None and calls == 1
    return True


async def _test_handler_deadline_allows_cleanup_rpc():
    async with _peers() as (caller, receiver):
        cleaned = asyncio.Event()

        @caller.register("cleanup")
        async def cleanup(payload):
            cleaned.set()
            return None

        @receiver.register("deadline")
        async def deadline(payload):
            try:
                await asyncio.Event().wait()
            finally:
                # Cleanup has its own deadline even when the outer request expired.
                await receiver.call(caller.name, "cleanup", None, timeout=RPC_TEST_TIMEOUT)

        request = caller._request(receiver.name, "deadline", None, timeout=0.1)
        await caller.transport.send(request)
        await asyncio.wait_for(cleaned.wait(), RPC_TEST_TIMEOUT)
        row = await _wait_status(request.task_id, "timeout")
        assert row.result["error"]["code"] == "timeout"
        (response,) = await caller.transport.consume_responses([request.task_id])
        assert response.status == "timeout"
        assert await JobQueuesTable.get_or_none(task_id=request.task_id) is None
        try:
            await caller.call("NO-RPC-RECEIVER", "missing", None, timeout=0.02)
            return False
        except RpcTimeoutError as exc:
            assert not caller._pending
            assert await JobQueuesTable.get_or_none(task_id=exc.task_id) is None
    return True


async def _test_expired_requests_skip_effects_and_global_limit_applies():
    async with _peers() as (caller, receiver):
        await receiver.begin_shutdown()
        effect = AsyncMock(return_value=True)
        receiver.register("effect", effect)
        request = replace(caller._request(receiver.name, "effect", None, 2), deadline=time.time() - 1)
        await caller.transport.send(request)
        task_id = request.task_id
        receiver.pause_event.set()
        row = await _wait_status(task_id, "timeout")
        assert row.result["error"]["code"] == "timeout"
        effect.assert_not_awaited()
        with patch.object(caller, "TASK_TIMEOUT_SECONDS", 0.01):
            request = caller._request(receiver.name, "effect", None, 100)
            assert request.deadline <= time.time() + 0.01
        for timeout in (True, False, 0, -1, float("nan"), float("inf"), "1"):
            try:
                await caller.submit(receiver.name, "effect", None, timeout=timeout)
                return False
            except ValueError:
                pass
    return True


async def _test_shutdown_failure_wakes_remote_caller():
    async with _peers() as (caller, receiver):
        started = asyncio.Event()

        @receiver.register("hang")
        async def hang(payload):
            started.set()
            await asyncio.Event().wait()

        task = asyncio.create_task(caller.call(receiver.name, "hang", None, timeout=RPC_TEST_TIMEOUT))
        await asyncio.wait_for(started.wait(), RPC_TEST_TIMEOUT)
        (task_id,) = caller._pending
        await receiver.begin_shutdown()
        await receiver.cancel_process_tasks()
        try:
            await asyncio.wait_for(task, 1)
            return False
        except RpcCancelledError:
            pass
        assert not caller._pending
        assert await JobQueuesTable.get_or_none(task_id=task_id) is None
    return True


async def _test_stopping_result_pump_wakes_local_waiters():
    async with _peers() as (caller, receiver):
        await receiver.begin_shutdown()
        task = asyncio.create_task(caller.call(receiver.name, "never", None, timeout=RPC_TEST_TIMEOUT))
        async with asyncio.timeout(RPC_TEST_TIMEOUT):
            while not caller._pending:
                await asyncio.sleep(0)
        (task_id,) = caller._pending
        await caller.stop_job_queue()
        try:
            await asyncio.wait_for(task, 1)
            return False
        except RpcUnavailableError:
            pass
        assert not caller._pending
        assert await JobQueuesTable.get_or_none(task_id=task_id) is None
    return True


async def _test_maintenance_pumps_nested_results_before_entering():
    async with _peers() as (caller, receiver):
        callback_started, finish_callback, entered = asyncio.Event(), asyncio.Event(), asyncio.Event()

        @caller.register("callback")
        async def callback(payload):
            callback_started.set()
            await finish_callback.wait()
            return "callback-done"

        @receiver.register("outer")
        async def outer(payload):
            return await receiver.call(caller.name, "callback", None, timeout=RPC_TEST_TIMEOUT)

        task = asyncio.create_task(caller.call(receiver.name, "outer", None, timeout=RPC_TEST_TIMEOUT))
        await asyncio.wait_for(callback_started.wait(), RPC_TEST_TIMEOUT)

        async def maintain():
            async with receiver.maintenance_window():
                entered.set()
                assert not receiver._pending

        maintenance = asyncio.create_task(maintain())
        await asyncio.sleep(0.02)
        assert not entered.is_set()
        finish_callback.set()
        result = await asyncio.wait_for(task, RPC_TEST_TIMEOUT)
        await asyncio.wait_for(maintenance, RPC_TEST_TIMEOUT)
        assert result == "callback-done" and entered.is_set() and receiver.pause_event.is_set()
    return True


async def _test_non_exclusive_maintenance_pumps_cleanup_rpc():
    """非独占维护窗口不得阻断清理阶段发起的响应回收。"""
    async with _peers() as (caller, receiver):

        @caller.register("cleanup")
        async def cleanup(payload):
            return payload

        async def maintain_and_cleanup():
            async with receiver.maintenance_window(exclusive=False):
                assert not receiver.pause_event.is_set()
                async with receiver.maintenance_window(exclusive=True):
                    assert receiver._maintenance_exclusive_owner is current
                assert receiver._maintenance_exclusive_owner is None
                return await receiver.call(caller.name, "cleanup", {"ok": True}, timeout=RPC_TEST_TIMEOUT)

        current = asyncio.current_task()
        result = await asyncio.wait_for(maintain_and_cleanup(), timeout=RPC_TEST_TIMEOUT)
        return (
            result == {"ok": True}
            and caller._maintenance_exclusive_owner is None
            and receiver._maintenance_exclusive_owner is None
        )


async def _test_bad_protocol_and_late_success_are_not_silent():
    async with _peers() as (caller, receiver):
        task_id = await JobQueuesTable.add_task(receiver.name, "legacy", {"old": "payload"})
        row = await _wait_status(task_id, "failed")
        assert row.result["error"]["code"] == "protocol_error"
        request = RpcRequest(str(row.task_id), receiver.name, "legacy", {}, time.time() + 1)
        try:
            caller._decode_response(request, RpcResponse(task_id, row.status, row.result))
            return False
        except RpcProtocolError:
            pass
        await receiver.transport.respond(
            request,
            RpcResponse(request.task_id, "done", {"rpc": PROTOCOL_VERSION, "value": "late"}),
        )
        row = await JobQueuesTable.get(task_id=task_id)
        assert row.status == "failed"
        malformed_error = RpcResponse(
            task_id,
            "failed",
            {"rpc": PROTOCOL_VERSION, "error": {"code": [], "message": "invalid"}},
        )
        try:
            caller._decode_response(request, malformed_error)
            return False
        except RpcProtocolError:
            pass
    return True


async def _test_ambiguous_send_failure_discards_possible_insert():
    """send 已落库后才抛错时，等待型调用仍应按未知结果清理已知任务 ID。"""
    async with _peers() as (caller, _receiver):
        original_send = caller.transport.send

        async def save_then_fail(request):
            await original_send(request)
            raise RuntimeError("ambiguous send failure")

        with patch.object(caller.transport, "send", new=save_then_fail):
            try:
                await caller.call("RPC-NO-RECEIVER", "ambiguous", None, timeout=1)
                return False
            except RuntimeError as exc:
                assert str(exc) == "ambiguous send failure"
        return (
            not caller._pending
            and not await JobQueuesTable.filter(
                source_peer_id=caller.name,
                action="ambiguous",
            ).exists()
        )


async def _test_response_cleanup_failure_does_not_hide_result():
    """终态结果已读入内存后，删除失败不得终止结果泵或改写调用结果。"""
    async with _peers() as (caller, receiver):

        @receiver.register("cleanup-failure")
        async def succeed(payload):
            return payload

        original_delete = QuerySet.delete

        async def fail_delete(query):
            if query.model is JobQueuesTable:
                raise RuntimeError("simulated cleanup failure")
            return await original_delete(query)

        with patch.object(QuerySet, "delete", new=fail_delete), patch.object(Logger, "exception") as logged:
            result = await caller.call(receiver.name, "cleanup-failure", {"ok": True}, timeout=RPC_TEST_TIMEOUT)
        rows = await JobQueuesTable.filter(source_peer_id=caller.name, action="cleanup-failure")
        await JobQueuesTable.filter(source_peer_id=caller.name, action="cleanup-failure").delete()
        return (
            result == {"ok": True}
            and len(rows) == 1
            and rows[0].status == "done"
            and logged.call_count >= 1
            and caller.is_running
        )


async def _test_malformed_deadline_is_protocol_failure():
    """bool 是 int 的子类，但不得被解释成合法的 Unix deadline。"""
    async with _peers() as (caller, receiver):
        request = replace(caller._request(receiver.name, "never", None, timeout=RPC_TEST_TIMEOUT), deadline=True)
        await caller.transport.send(request)
        row = await _wait_status(request.task_id, "failed")
        (response,) = await caller.transport.consume_responses([request.task_id])
        return row.result["error"]["code"] == "protocol_error" and response.status == "failed"


async def _test_nested_maintenance_window_is_reentrant_for_owner():
    """同一任务嵌套维护窗口时复用外层锁，避免不可重入锁导致死锁。"""
    async with _peers() as (caller, _receiver):
        async with asyncio.timeout(RPC_TEST_TIMEOUT):
            async with caller.maintenance_window():
                assert not caller.pause_event.is_set()
                async with caller.maintenance_window():
                    assert not caller.pause_event.is_set()
                assert not caller.pause_event.is_set()
        return caller.pause_event.is_set() and caller._maintenance_owner is None


async def _test_concurrent_maintenance_windows_are_serialized():
    """不同任务的维护窗口必须串行，避免后进入者在 Registry 已恢复 ready 后执行维护。"""
    async with _peers() as (caller, _receiver):
        first_entered = asyncio.Event()
        release_first = asyncio.Event()
        second_entered = asyncio.Event()

        async def first():
            async with caller.maintenance_window():
                first_entered.set()
                await release_first.wait()

        async def second():
            await first_entered.wait()
            async with caller.maintenance_window():
                second_entered.set()

        first_task = asyncio.create_task(first())
        second_task = asyncio.create_task(second())
        try:
            await asyncio.wait_for(first_entered.wait(), RPC_TEST_TIMEOUT)
            await asyncio.sleep(0.02)
            serialized = not second_entered.is_set()
            release_first.set()
            await asyncio.wait_for(asyncio.gather(first_task, second_task), RPC_TEST_TIMEOUT)
            return serialized and second_entered.is_set() and caller.pause_event.is_set()
        finally:
            release_first.set()
            for task in (first_task, second_task):
                if not task.done():
                    task.cancel()
            await asyncio.gather(first_task, second_task, return_exceptions=True)


@func_case
async def test_rpc_transport(tester: Tester):
    await tester.test(_test_roundtrip_preserves_json_and_registry_isolation, "RPC 空值与 peer 状态隔离")
    await tester.test(_test_bidirectional_nested_calls, "双向嵌套 RPC 并发回包")
    await tester.test(_test_remote_errors_and_invalid_method_are_distinct, "远端异常与未知方法独立错误")
    await tester.test(_test_local_cancellation_does_not_cancel_or_retry_remote_effect, "取消等待不取消或重试远端副作用")
    await tester.test(_test_handler_deadline_allows_cleanup_rpc, "执行超时仍能完成清理 RPC")
    await tester.test(_test_expired_requests_skip_effects_and_global_limit_applies, "过期请求不执行且限制全局上限")
    await tester.test(_test_shutdown_failure_wakes_remote_caller, "接收方关闭唤醒调用方")
    await tester.test(_test_stopping_result_pump_wakes_local_waiters, "结果泵关闭释放本地等待")
    await tester.test(_test_maintenance_pumps_nested_results_before_entering, "维护前排空双向在途调用")
    await tester.test(_test_non_exclusive_maintenance_pumps_cleanup_rpc, "非独占维护仍可回收清理 RPC 响应")
    await tester.test(_test_bad_protocol_and_late_success_are_not_silent, "旧协议明确失败且终态不被覆盖")
    await tester.test(_test_ambiguous_send_failure_discards_possible_insert, "投递结果未知时清理可能已写入的任务")
    await tester.test(_test_response_cleanup_failure_does_not_hide_result, "结果删除失败不掩盖已读取结果")
    await tester.test(_test_malformed_deadline_is_protocol_failure, "非法布尔 deadline 明确返回协议错误")
    await tester.test(_test_nested_maintenance_window_is_reentrant_for_owner, "同任务嵌套维护窗口不会自锁")
    await tester.test(_test_concurrent_maintenance_windows_are_serialized, "并发维护窗口串行执行")
    return tester
