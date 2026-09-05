"""RPC runtime tests over real database rows, including lifecycle boundaries."""

import asyncio
import time
from contextlib import asynccontextmanager
from dataclasses import replace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from core.database.models import JobQueuesTable
from core.queue.base import current_peer, JobQueueBase
from core.queue.errors import (
    RpcCancelledError,
    RpcMethodNotFoundError,
    RpcProtocolError,
    RpcRemoteError,
    RpcTimeoutError,
    RpcUnavailableError,
)
from core.queue.transport import RpcRequest, RpcResponse
from core.tester import func_case, Tester


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
        await JobQueuesTable.filter(target_client__in=[Caller.name, Receiver.name]).delete()


async def _wait_status(task_id, status):
    async with asyncio.timeout(2):
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
        results = await asyncio.gather(*(caller.call(receiver.name, "echo", value, timeout=2) for value in values))
        assert results == values
        assert "echo" not in caller.handlers
        assert caller._pending is not receiver._pending
        assert caller._process_tasks is not receiver._process_tasks
        assert caller.pause_event is not receiver.pause_event
        assert current_peer.get() is None
        assert not caller._pending
    return True


async def _test_bidirectional_nested_calls():
    async with _peers() as (caller, receiver):

        @caller.register("callback")
        async def callback(payload):
            return {"value": payload["value"] + 1}

        @receiver.register("outer")
        async def outer(payload):
            return await current_peer.get().call(caller.name, "callback", payload, timeout=2)

        result = await asyncio.gather(*(caller.call(receiver.name, "outer", {"value": n}, timeout=2) for n in range(8)))
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
                await caller.call(receiver.name, "broken", {}, timeout=2)
                return False
            except RpcRemoteError as exc:
                assert exc.remote_type == "ValueError"
                assert exc.method == "broken" and exc.target == receiver.name and exc.task_id
                assert str(exc) == "deliberate handler failure"
            try:
                await caller.call(receiver.name, "missing", {}, timeout=2)
                return False
            except RpcMethodNotFoundError:
                pass
            try:
                await caller.call(receiver.name, "application_timeout", {}, timeout=2)
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

        task = asyncio.create_task(caller.call(receiver.name, "effect", None, timeout=2))
        await asyncio.wait_for(started.wait(), 1)
        (task_id,) = caller._pending
        task.cancel()
        (result,) = await asyncio.gather(task, return_exceptions=True)
        assert isinstance(result, asyncio.CancelledError)
        assert not caller._pending
        proceed.set()
        row = await _wait_status(task_id, "done")
        assert row.result["value"] == "effect-completed" and calls == 1
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
                await receiver.call(caller.name, "cleanup", None, timeout=1)

        task_id = await caller.submit(receiver.name, "deadline", None, timeout=0.1)
        await asyncio.wait_for(cleaned.wait(), 1)
        row = await _wait_status(task_id, "timeout")
        assert row.result["error"]["code"] == "timeout"
        try:
            await caller.call("NO-RPC-RECEIVER", "missing", None, timeout=0.02)
            return False
        except RpcTimeoutError:
            assert not caller._pending
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
        for timeout in (0, -1, float("nan"), float("inf")):
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

        task = asyncio.create_task(caller.call(receiver.name, "hang", None, timeout=2))
        await asyncio.wait_for(started.wait(), 1)
        await receiver.begin_shutdown()
        await receiver.cancel_process_tasks()
        try:
            await asyncio.wait_for(task, 1)
            return False
        except RpcCancelledError:
            pass
        assert not caller._pending
    return True


async def _test_stopping_result_pump_wakes_local_waiters():
    async with _peers() as (caller, receiver):
        await receiver.begin_shutdown()
        task = asyncio.create_task(caller.call(receiver.name, "never", None, timeout=2))
        async with asyncio.timeout(1):
            while not caller._pending:
                await asyncio.sleep(0)
        await caller.stop_job_queue()
        try:
            await asyncio.wait_for(task, 1)
            return False
        except RpcUnavailableError:
            pass
        assert not caller._pending
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
            return await receiver.call(caller.name, "callback", None, timeout=2)

        task = asyncio.create_task(caller.call(receiver.name, "outer", None, timeout=2))
        await asyncio.wait_for(callback_started.wait(), 1)

        async def maintain():
            async with receiver.maintenance_window():
                entered.set()
                assert not receiver._pending

        maintenance = asyncio.create_task(maintain())
        await asyncio.sleep(0.02)
        assert not entered.is_set()
        finish_callback.set()
        result = await asyncio.wait_for(task, 1)
        await asyncio.wait_for(maintenance, 1)
        assert result == "callback-done" and entered.is_set() and receiver.pause_event.is_set()
    return True


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
        await receiver.transport.finish(RpcResponse(task_id, "done", {"rpc": 1, "value": "late"}))
        row = await JobQueuesTable.get(task_id=task_id)
        assert row.status == "failed"
    return True


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
    await tester.test(_test_bad_protocol_and_late_success_are_not_silent, "旧协议明确失败且终态不被覆盖")
    return tester
