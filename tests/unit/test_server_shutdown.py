"""Server 优雅退出与 JobQueue 收束路径测试。"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from core.database.models import JobQueuesTable
from core.queue.base import JobQueueBase
from core.server import run as server_run
from core.server import terminate as server_terminate
from core.tester import Tester, func_case


async def _test_cleanup_sessions_clears_jobs_created_during_shutdown() -> bool:
    """停止资源期间产生的队列记录也必须由最后一次清表移除。"""
    initial_action = "test_shutdown_initial"
    late_action = "test_shutdown_late"
    close_web_render = AsyncMock()

    async def _close_web_render_with_late_job() -> None:
        await JobQueuesTable.add_task("Server", late_action, {})

    close_web_render.side_effect = _close_web_render_with_late_job
    try:
        await JobQueuesTable.add_task("Server", initial_action, {})
        with (
            patch.object(server_terminate.Scheduler, "shutdown") as scheduler_shutdown,
            patch.object(server_terminate, "close_web_render", new=close_web_render),
            patch.object(server_terminate.Tortoise, "close_connections", new=AsyncMock()) as close_connections,
        ):
            await server_terminate.cleanup_sessions()

        remaining = await JobQueuesTable.filter(action__in=[initial_action, late_action]).count()
        return (
            remaining == 0
            and scheduler_shutdown.call_count == 1
            and close_web_render.await_count == 1
            and close_connections.await_count == 1
        )
    except Exception:
        return False
    finally:
        await JobQueuesTable.filter(action__in=[initial_action, late_action]).delete()


async def _test_process_stop_event_runs_server_cleanup() -> bool:
    """守护进程的停止事件应退出 Server 主循环并进入清理流程。"""
    cleanup_sessions = AsyncMock(return_value=True)
    queue_started = asyncio.Event()
    queue_cancelled = asyncio.Event()

    async def _check_job_queue() -> None:
        queue_started.set()
        try:
            await asyncio.Event().wait()
        finally:
            queue_cancelled.set()

    async def _load_prompt(_locale_errors) -> None:
        await asyncio.sleep(0)

    shutdown_workers = AsyncMock()
    server_run.stop_event = None
    try:
        with (
            patch.object(server_run, "build_locale_snapshot", return_value=[]),
            patch.object(server_run, "connect_locale_snapshot"),
            patch.object(server_run, "init_async", new=AsyncMock()),
            patch.object(server_run, "restore_alive_clients"),
            patch.object(server_run.JobQueueServer, "check_job_queue", side_effect=_check_job_queue),
            patch.object(server_run.JobQueueServer, "shutdown_workers", new=shutdown_workers),
            patch.object(server_run, "load_prompt", side_effect=_load_prompt),
            patch.object(server_run, "cleanup_sessions", new=cleanup_sessions),
        ):
            process_stop_event = SimpleNamespace(is_set=lambda: True)
            await asyncio.wait_for(server_run.main(process_stop_event), timeout=2)

        return (
            queue_started.is_set()
            and queue_cancelled.is_set()
            and shutdown_workers.await_count == 1
            and cleanup_sessions.await_count == 1
        )
    except Exception:
        return False
    finally:
        server_run.stop_event = None


async def _test_process_stop_event_interrupts_initialization() -> bool:
    """停止事件在初始化阶段到达时，也必须取消初始化并执行清理。"""
    cleanup_sessions = AsyncMock(return_value=True)
    init_started = asyncio.Event()
    init_cancelled = asyncio.Event()
    state = {"stop": False}

    async def _init_async(send_prompt=False) -> None:
        del send_prompt
        init_started.set()
        try:
            await asyncio.Event().wait()
        finally:
            init_cancelled.set()

    server_run.stop_event = None
    try:
        with (
            patch.object(server_run, "build_locale_snapshot", return_value=[]),
            patch.object(server_run, "connect_locale_snapshot"),
            patch.object(server_run, "init_async", side_effect=_init_async),
            patch.object(server_run.JobQueueServer, "shutdown_workers", new=AsyncMock()),
            patch.object(server_run, "cleanup_sessions", new=cleanup_sessions),
        ):
            process_stop_event = SimpleNamespace(is_set=lambda: state["stop"])
            server_task = asyncio.create_task(server_run.main(process_stop_event))
            await asyncio.wait_for(init_started.wait(), timeout=1)
            state["stop"] = True
            await asyncio.wait_for(server_task, timeout=2)

        return init_cancelled.is_set() and cleanup_sessions.await_count == 1
    except Exception:
        return False
    finally:
        server_run.stop_event = None


async def _test_worker_shutdown_has_no_late_writer() -> bool:
    """worker 收束返回后，不应再有延迟写入或存活任务。"""

    class ShutdownQueue(JobQueueBase):
        pass

    started = asyncio.Event()
    writes = []

    async def _worker() -> None:
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            # 模拟 worker 在取消清理阶段最后一次触碰持久化状态。
            await asyncio.sleep(0)
            writes.append("settled")

    worker = asyncio.create_task(_worker())
    ShutdownQueue._worker_tasks.add(worker)
    worker.add_done_callback(ShutdownQueue._worker_tasks.discard)
    try:
        await started.wait()
        await asyncio.wait_for(ShutdownQueue.shutdown_workers(), timeout=2)
        writes_at_return = tuple(writes)
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        return (
            worker.done()
            and not ShutdownQueue._worker_tasks
            and writes_at_return == ("settled",)
            and tuple(writes) == writes_at_return
        )
    except Exception:
        return False
    finally:
        if not worker.done():
            worker.cancel()
            await asyncio.gather(worker, return_exceptions=True)


async def _test_restart_stops_workers_before_cleanup() -> bool:
    """内部重启也必须先收束 worker，再执行最终清表。"""
    order = []

    async def _shutdown_workers() -> None:
        order.append("workers")

    async def _cleanup_sessions() -> bool:
        order.append("cleanup")
        return True

    with (
        patch.object(server_terminate, "cache_alive_clients"),
        patch.object(server_terminate, "cleanup_sessions", side_effect=_cleanup_sessions),
        patch.object(server_terminate.os, "_exit") as process_exit,
        patch("core.queue.server.JobQueueServer.shutdown_workers", side_effect=_shutdown_workers),
    ):
        await server_terminate.restart(server_only=True)

    return order == ["workers", "cleanup"] and process_exit.call_count == 1


@func_case
async def test_server_shutdown(tester: Tester):
    """Server：守护进程停止事件与最终 JobQueue 清理测试。"""
    await tester.test(
        _test_cleanup_sessions_clears_jobs_created_during_shutdown,
        "资源停止期间产生的 JobQueue 记录仍会被最终清空",
    )
    await tester.test(
        _test_process_stop_event_runs_server_cleanup,
        "process_stop_event 会终止 Server 轮询并执行清理",
    )
    await tester.test(
        _test_process_stop_event_interrupts_initialization,
        "process_stop_event 可中断 Server 初始化并执行清理",
    )
    await tester.test(
        _test_worker_shutdown_has_no_late_writer,
        "JobQueue worker 收束返回后不会再延迟写入",
    )
    await tester.test(
        _test_restart_stops_workers_before_cleanup,
        "内部重启会先收束 JobQueue worker 再清表",
    )
    return tester
