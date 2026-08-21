"""Server、客户端与消息入口的后台任务生命周期测试。"""

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import core.builtins.bot as bot_module
import core.client.init as client_init_module
import core.server.background_tasks as background_tasks
import core.server.init as server_init
import core.server.lifecycle as server_lifecycle
import core.server.run as server_run
import core.server.terminate as server_terminate
import core.web_render as web_render_module
from core.builtins.session.features import Features
from core.builtins.session.info import SessionInfo
from core.exports import exports
from core.tester import Tester, func_case


async def _test_server_init_failure_still_cleans_up() -> bool:
    """初始化中途失败也必须走统一关闭流程。"""
    cleanup = AsyncMock()
    server_run.stop_event.clear()
    with (
        patch.object(server_run, "build_locale_snapshot", return_value=[]),
        patch.object(server_run, "connect_locale_snapshot"),
        patch.object(server_run, "init_async", new=AsyncMock(side_effect=RuntimeError("init failed"))),
        patch.object(server_run, "cleanup_sessions", new=cleanup),
    ):
        try:
            await server_run.main()
        except RuntimeError as exc:
            return str(exc) == "init failed" and cleanup.await_count == 1
    return False


async def _test_server_notices_dead_queue_poller() -> bool:
    """队列轮询异常退出时 Server 应失败退出，交由守护进程重启。"""
    cleanup = AsyncMock()
    server_run.stop_event.clear()

    async def fail_queue():
        raise RuntimeError("queue poller failed")

    with (
        patch.object(server_run, "build_locale_snapshot", return_value=[]),
        patch.object(server_run, "connect_locale_snapshot"),
        patch.object(server_run, "init_async", new=AsyncMock()),
        patch.object(server_run, "load_prompt", new=AsyncMock()),
        patch.object(server_run.JobQueueServer, "check_job_queue", new=fail_queue),
        patch.object(server_run, "cleanup_sessions", new=cleanup),
    ):
        try:
            await asyncio.wait_for(server_run.main(), timeout=1)
        except RuntimeError as exc:
            return str(exc) == "queue poller failed" and cleanup.await_count == 1
        except asyncio.TimeoutError:
            return False
    return False


async def _test_server_keeps_queue_poller_alive_for_cleanup() -> bool:
    """统一清理需要先使用 Queue 释放后台 context，再停止轮询器。"""
    queue_started = asyncio.Event()
    queue_stopped = asyncio.Event()
    cleanup_saw_live_queue = False

    async def queue_poller():
        queue_started.set()
        try:
            await asyncio.Event().wait()
        finally:
            queue_stopped.set()

    async def load_prompt(_):
        await queue_started.wait()

    async def cleanup():
        nonlocal cleanup_saw_live_queue
        cleanup_saw_live_queue = not queue_stopped.is_set()

    process_stop_event = SimpleNamespace(is_set=lambda: True)
    server_run.stop_event.clear()
    with (
        patch.object(server_run, "build_locale_snapshot", return_value=[]),
        patch.object(server_run, "connect_locale_snapshot"),
        patch.object(server_run, "init_async", new=AsyncMock()),
        patch.object(server_run, "load_prompt", new=load_prompt),
        patch.object(server_run.JobQueueServer, "check_job_queue", new=queue_poller),
        patch.object(server_run, "cleanup_sessions", new=cleanup),
    ):
        await server_run.main(process_stop_event)

    return cleanup_saw_live_queue and queue_stopped.is_set()


async def _test_shutdown_cancels_background_initialization() -> bool:
    """关闭 Server 时必须取消并等待尚未完成的 WebRender/IP 初始化。"""
    started = asyncio.Event()
    stopped = asyncio.Event()
    release = asyncio.Event()

    async def slow_background_init():
        started.set()
        try:
            await release.wait()
        finally:
            stopped.set()

    stop_background = getattr(background_tasks, "stop_background_task", None)
    if stop_background:
        await stop_background()

    pending_before = set(asyncio.all_tasks())
    try:
        with (
            patch.object(server_init, "init_db", new=AsyncMock(return_value=True)),
            patch.object(server_init, "load_modules", new=AsyncMock()),
            patch.object(server_init.ModulesManager, "return_modules_list", return_value={}),
            patch.object(server_init, "run_sys_command", new=AsyncMock(return_value=(1, "", ""))),
            patch.object(server_init, "load_secret", new=AsyncMock()),
            patch.object(server_init, "init_background_task", new=slow_background_init, create=True),
            patch.object(background_tasks, "init_background_task", new=slow_background_init),
            patch.object(server_terminate.JobQueuesTable, "clear_task", new=AsyncMock()),
            patch.object(server_terminate.SchedulerLifecycle, "begin_shutdown"),
            patch.object(server_terminate.SchedulerLifecycle, "shutdown", new=AsyncMock()),
            patch.object(server_terminate.BackgroundTaskLifecycle, "run_cleanup", new=AsyncMock()),
            patch.object(server_terminate, "close_web_render", new=AsyncMock()),
            patch.object(server_terminate.Tortoise, "close_connections", new=AsyncMock()),
        ):
            await server_init.init_async(start_scheduler=False)
            await asyncio.wait_for(started.wait(), timeout=1)
            await server_terminate.cleanup_sessions()
            await asyncio.sleep(0)
            return stopped.is_set()
    finally:
        release.set()
        stop_background = getattr(background_tasks, "stop_background_task", None)
        if stop_background:
            await stop_background()
        pending_after = [task for task in asyncio.all_tasks() - pending_before if task is not asyncio.current_task()]
        for task in pending_after:
            if not task.done():
                task.cancel()
        await asyncio.gather(*pending_after, return_exceptions=True)


async def _test_background_init_cancels_failed_sibling() -> bool:
    """一项后台初始化异常时，另一项必须被取消并等待，不能脱离父任务继续运行。"""
    render_started = asyncio.Event()
    render_stopped = asyncio.Event()
    release = asyncio.Event()

    async def slow_web_render():
        render_started.set()
        try:
            await release.wait()
        finally:
            render_stopped.set()

    async def failed_ip_info():
        await render_started.wait()
        raise RuntimeError("ip init failed")

    failed = False
    try:
        with (
            patch.object(background_tasks, "fetch_ip_info", new=failed_ip_info),
            patch.object(background_tasks, "init_web_render", new=slow_web_render),
        ):
            try:
                await background_tasks.init_background_task()
            except BaseExceptionGroup as exc:
                failed = any(isinstance(error, RuntimeError) for error in exc.exceptions)
        return failed and render_stopped.is_set()
    finally:
        release.set()


async def _test_remote_only_webrender_uses_remote_health() -> bool:
    """remote_only 只能检查远端状态，不能启动或关闭本地浏览器。"""
    browser_init = AsyncMock(return_value=True)
    browser_close = AsyncMock(return_value=True)
    remote_status = AsyncMock(return_value={"browser_initialized": True, "remote_only": True})
    with (
        patch.object(web_render_module, "enable_web_render", True),
        patch.object(web_render_module, "remote_only", True),
        patch.object(web_render_module.web_render, "browser_init", new=browser_init),
        patch.object(web_render_module.web_render, "browser_close", new=browser_close),
        patch.object(web_render_module.web_render, "status", new=remote_status),
    ):
        initialized = await web_render_module.init_web_render()
        checked = await web_render_module.check_web_render_status()
        closed = await web_render_module.close_web_render()
    return (
        initialized
        and checked
        and closed
        and browser_init.await_count == 0
        and browser_close.await_count == 0
        and remote_status.await_count == 2
    )


async def _test_background_init_uses_configured_webrender_health() -> bool:
    """后台状态必须来自统一健康检查，而不是只读取本地浏览器。"""
    previous_status = background_tasks.Info.web_render_status
    try:
        with (
            patch.object(background_tasks, "fetch_ip_info", new=AsyncMock()),
            patch.object(background_tasks, "init_web_render", new=AsyncMock(return_value=True)),
            patch.object(background_tasks, "check_web_render_status", new=AsyncMock(return_value=True)),
        ):
            await background_tasks.init_background_task()
        return background_tasks.Info.web_render_status is True
    finally:
        background_tasks.Info.web_render_status = previous_status


async def _test_client_queue_poller_recovers_from_transient_failure() -> bool:
    """客户端队列轮询遇到一次异常后应自动恢复，而不是永久失联。"""
    calls = 0
    restarted = asyncio.Event()
    release = asyncio.Event()

    async def flaky_queue_poller():
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("temporary database failure")
        restarted.set()
        await release.wait()

    old_queue_task = client_init_module._queue_task
    old_keepalive_task = client_init_module._keepalive_task
    old_initialization_task = client_init_module._initialization_task
    client_init_module._queue_task = None
    client_init_module._keepalive_task = None
    client_init_module._initialization_task = None
    try:
        with (
            patch.object(client_init_module, "init_db", new=AsyncMock(return_value=True)),
            patch.object(client_init_module.JobQueueClient, "check_job_queue", new=flaky_queue_poller),
            patch.object(
                client_init_module.JobQueueClient,
                "send_keepalive_signal_to_server",
                new=AsyncMock(),
            ),
            patch.object(client_init_module.Bot, "ContextSlots", [SimpleNamespace(features=Features())]),
            patch.object(client_init_module.Bot, "fetched_session_ctx_slot", 0),
            patch.object(client_init_module, "connect_locale_snapshot"),
        ):
            await client_init_module.client_init(rename_logger=False)
            try:
                await asyncio.wait_for(restarted.wait(), timeout=1)
            except asyncio.TimeoutError:
                return False
            return (
                calls >= 2 and client_init_module._queue_task is not None and not client_init_module._queue_task.done()
            )
    finally:
        release.set()
        tasks = [client_init_module._queue_task, client_init_module._keepalive_task]
        for task in tasks:
            if task is not None and not task.done():
                task.cancel()
        await asyncio.gather(*(task for task in tasks if task is not None), return_exceptions=True)
        client_init_module._queue_task = old_queue_task
        client_init_module._keepalive_task = old_keepalive_task
        client_init_module._initialization_task = old_initialization_task


async def _test_message_background_failure_is_observed_and_cleaned() -> bool:
    """消息后台任务失败后应记录异常、释放 Context，并从任务集合移除。"""
    deleted = asyncio.Event()

    class FakeContextManager:
        features = Features()

        @staticmethod
        def add_context(session_info, ctx):
            return None

        @staticmethod
        def del_context(session_info):
            deleted.set()

    class FailingQueueClient:
        @staticmethod
        async def send_message_to_server(session_info):
            raise RuntimeError("queue write failed")

    old_slots = bot_module.Bot.ContextSlots
    old_queue_client = exports.get("JobQueueClient")
    bot_module.Bot.ContextSlots = [FakeContextManager()]
    exports["JobQueueClient"] = FailingQueueClient
    session = SessionInfo(
        target_id="Lifecycle|Group|1",
        target_from="Lifecycle|Group",
        client_name="Lifecycle",
        sender_id="Lifecycle|1",
        sender_from="Lifecycle",
        session_id="lifecycle-message",
        ctx_slot=0,
    )
    try:
        with patch.object(bot_module.Logger, "exception") as log_exception:
            await bot_module.Bot.process_message(session, object())
            await asyncio.wait_for(deleted.wait(), timeout=1)
            await asyncio.sleep(0)
            pending = getattr(bot_module.Bot, "_message_tasks", None)
            return log_exception.call_count == 1 and pending is not None and not pending
    finally:
        tasks = list(getattr(bot_module.Bot, "_message_tasks", ()))
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        bot_module.Bot.ContextSlots = old_slots
        if old_queue_client is None:
            exports.pop("JobQueueClient", None)
        else:
            exports["JobQueueClient"] = old_queue_client


async def _test_shutdown_waits_for_inflight_queue_handlers() -> bool:
    """关闭时须取消并等待已领取、仍在执行的队列 action。"""
    process_tasks = getattr(server_run.JobQueueServer, "_process_tasks", None)
    if process_tasks is None:
        return False

    started = asyncio.Event()
    stopped = asyncio.Event()

    async def handler():
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    task = asyncio.create_task(handler(), name="test-inflight-queue-handler")
    process_tasks.add(task)
    await asyncio.wait_for(started.wait(), timeout=1)
    try:
        with (
            patch.object(server_terminate.JobQueuesTable, "clear_task", new=AsyncMock()),
            patch.object(server_terminate.SchedulerLifecycle, "begin_shutdown"),
            patch.object(server_terminate.SchedulerLifecycle, "shutdown", new=AsyncMock()),
            patch.object(server_terminate, "stop_background_task", new=AsyncMock()),
            patch.object(server_terminate.BackgroundTaskLifecycle, "run_cleanup", new=AsyncMock()),
            patch.object(server_terminate, "close_web_render", new=AsyncMock()),
            patch.object(server_terminate.Tortoise, "close_connections", new=AsyncMock()),
        ):
            await server_terminate.cleanup_sessions()
        return stopped.is_set() and task.done() and task not in process_tasks
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        process_tasks.discard(task)


async def _test_shutdown_prevents_new_queue_claims() -> bool:
    """清理队列和关闭数据库期间，仍存活的轮询器不得领取新的 action。"""
    queue = server_run.JobQueueServer
    old_running = queue.is_running
    queue.is_running = False
    claims = 0
    cleanup_started = asyncio.Event()
    allow_cleanup = asyncio.Event()
    claimed_during_cleanup = False

    async def check_queue(target_client=None, claim_new=True):
        nonlocal claims, claimed_during_cleanup
        if claim_new:
            claims += 1
            if cleanup_started.is_set() and not allow_cleanup.is_set():
                claimed_during_cleanup = True

    async def clear_task(*args, **kwargs):
        cleanup_started.set()
        # 给轮询器多次调度机会；正确实现会因 shutdown_window 持有轮询锁而无法进入。
        for _ in range(5):
            await asyncio.sleep(0)
        allow_cleanup.set()

    poller = None
    try:
        with (
            patch.object(queue, "_check_queue", new=check_queue),
            patch.object(server_terminate.JobQueuesTable, "clear_task", new=clear_task),
            patch.object(server_terminate.SchedulerLifecycle, "begin_shutdown"),
            patch.object(server_terminate.SchedulerLifecycle, "shutdown", new=AsyncMock()),
            patch.object(server_terminate, "stop_background_task", new=AsyncMock()),
            patch.object(server_terminate.BackgroundTaskLifecycle, "run_cleanup", new=AsyncMock()),
            patch.object(server_terminate, "close_web_render", new=AsyncMock()),
            patch.object(server_terminate.Tortoise, "close_connections", new=AsyncMock()),
        ):
            poller = asyncio.create_task(queue.check_job_queue(), name="test-server-queue-poller")
            while claims == 0:
                await asyncio.sleep(0)
            await server_terminate.cleanup_sessions()
        return (
            cleanup_started.is_set()
            and allow_cleanup.is_set()
            and not claimed_during_cleanup
            and poller.done()
            and queue._poller_task is None
        )
    finally:
        if poller is not None and not poller.done():
            poller.cancel()
        if poller is not None:
            await asyncio.gather(poller, return_exceptions=True)
        queue.is_running = old_running
        queue.pause_event.set()


async def _test_background_cleanup_registry_is_generic_and_reload_safe() -> bool:
    """任意组件可注册清理，同一稳定 key 的热重载只保留最新回调。"""
    calls = []

    async def old_cleanup():
        calls.append("old")

    async def second_cleanup():
        calls.append("second")

    async def new_cleanup():
        calls.append("new")

    with patch.dict(server_lifecycle.BackgroundTaskLifecycle._cleanup_hooks, {}, clear=True):
        server_lifecycle.BackgroundTaskLifecycle.register_cleanup("test:replace", old_cleanup)
        server_lifecycle.BackgroundTaskLifecycle.register_cleanup("test:second", second_cleanup)
        server_lifecycle.BackgroundTaskLifecycle.register_cleanup("test:replace", new_cleanup)
        await server_lifecycle.BackgroundTaskLifecycle.run_cleanup()
        return calls == ["new", "second"] and list(server_lifecycle.BackgroundTaskLifecycle._cleanup_hooks) == [
            "test:replace",
            "test:second",
        ]


async def _test_background_cleanup_isolates_failure_and_timeout() -> bool:
    """单项清理失败或超时不得阻断后续组件关闭。"""
    calls = []
    timed_out = asyncio.Event()

    async def failed_cleanup():
        calls.append("failed")
        raise RuntimeError("cleanup failed")

    async def slow_cleanup():
        try:
            await asyncio.Event().wait()
        finally:
            timed_out.set()

    async def healthy_cleanup():
        calls.append("healthy")

    with (
        patch.dict(server_lifecycle.BackgroundTaskLifecycle._cleanup_hooks, {}, clear=True),
        patch.object(server_lifecycle.Logger, "exception") as log_exception,
        patch.object(server_lifecycle.Logger, "warning") as log_warning,
    ):
        server_lifecycle.BackgroundTaskLifecycle.register_cleanup("test:failed", failed_cleanup)
        server_lifecycle.BackgroundTaskLifecycle.register_cleanup("test:timeout", slow_cleanup, timeout=0.01)
        server_lifecycle.BackgroundTaskLifecycle.register_cleanup("test:healthy", healthy_cleanup)
        await server_lifecycle.BackgroundTaskLifecycle.run_cleanup()
        return (
            calls == ["failed", "healthy"]
            and timed_out.is_set()
            and log_exception.call_count == 1
            and log_warning.call_count == 1
        )


async def _test_shutdown_cleanup_keeps_result_pump_without_new_claims() -> bool:
    """模块清理期间 Queue 只回收远端结果，不再领取新的 action。"""
    queue = server_run.JobQueueServer
    old_running = queue.is_running
    old_shutting_down = queue._shutting_down
    queue.is_running = False
    first_claim = asyncio.Event()
    cleanup_started = asyncio.Event()
    result_reaped = asyncio.Event()
    claimed_during_cleanup = False

    async def check_queue(target_client=None, claim_new=True):
        nonlocal claimed_during_cleanup
        if claim_new:
            if cleanup_started.is_set():
                claimed_during_cleanup = True
            first_claim.set()
        elif cleanup_started.is_set():
            result_reaped.set()

    async def cleanup_registered_tasks():
        cleanup_started.set()
        await asyncio.wait_for(result_reaped.wait(), timeout=1)

    poller = None
    try:
        with (
            patch.object(queue, "_check_queue", new=check_queue),
            patch.object(server_terminate.SchedulerLifecycle, "begin_shutdown"),
            patch.object(server_terminate.SchedulerLifecycle, "shutdown", new=AsyncMock()),
            patch.object(server_terminate, "stop_background_task", new=AsyncMock()),
            patch.object(
                server_terminate.BackgroundTaskLifecycle,
                "run_cleanup",
                new=cleanup_registered_tasks,
            ),
            patch.object(server_terminate.JobQueuesTable, "clear_task", new=AsyncMock()),
            patch.object(server_terminate, "close_web_render", new=AsyncMock()),
            patch.object(server_terminate.Tortoise, "close_connections", new=AsyncMock()),
        ):
            poller = asyncio.create_task(queue.check_job_queue(), name="test-server-result-pump")
            await asyncio.wait_for(first_claim.wait(), timeout=1)
            await asyncio.wait_for(server_terminate.cleanup_sessions(), timeout=2)
        return result_reaped.is_set() and not claimed_during_cleanup and poller.done() and queue._poller_task is None
    finally:
        if poller is not None and not poller.done():
            poller.cancel()
        if poller is not None:
            await asyncio.gather(poller, return_exceptions=True)
        queue.is_running = old_running
        queue._shutting_down = old_shutting_down
        queue.pause_event.set()


async def _test_shutdown_runs_registered_cleanup_before_queue_stop() -> bool:
    """通用后台清理必须在新任务入口和生产者停止后、Queue 停止前执行。"""
    calls = []

    def begin_scheduler_shutdown():
        calls.append("scheduler-begin")

    async def begin_queue_shutdown():
        calls.append("queue-begin")

    async def cancel_queue_handlers():
        calls.append("queue-handlers")

    async def shutdown_scheduler():
        calls.append("scheduler-stop")

    async def stop_background():
        calls.append("background-init")

    async def cleanup_registered():
        calls.append("registered-background")

    async def stop_queue():
        calls.append("queue")

    async def clear_task(*args, **kwargs):
        calls.append("clear")

    async def close_connections():
        calls.append("database")

    @asynccontextmanager
    async def shutdown_window():
        calls.append("window-enter")
        yield
        calls.append("window-exit")

    with (
        patch.object(server_terminate.SchedulerLifecycle, "begin_shutdown", new=begin_scheduler_shutdown),
        patch.object(server_terminate.SchedulerLifecycle, "shutdown", new=shutdown_scheduler),
        patch.object(server_terminate.JobQueueServer, "begin_shutdown", new=begin_queue_shutdown),
        patch.object(server_terminate.JobQueueServer, "cancel_process_tasks", new=cancel_queue_handlers),
        patch.object(server_terminate, "stop_background_task", new=stop_background),
        patch.object(server_terminate.BackgroundTaskLifecycle, "run_cleanup", new=cleanup_registered),
        patch.object(server_terminate.JobQueueServer, "shutdown_window", new=shutdown_window),
        patch.object(server_terminate.JobQueueServer, "stop_job_queue", new=stop_queue),
        patch.object(server_terminate.JobQueuesTable, "clear_task", new=clear_task),
        patch.object(server_terminate, "close_web_render", new=AsyncMock()),
        patch.object(server_terminate.Tortoise, "close_connections", new=close_connections),
    ):
        await server_terminate.cleanup_sessions()

    return calls == [
        "scheduler-begin",
        "queue-begin",
        "queue-handlers",
        "scheduler-stop",
        "background-init",
        "registered-background",
        "window-enter",
        "queue",
        "clear",
        "database",
        "window-exit",
    ]


@func_case
async def test_runtime_lifecycle(tester: Tester):
    """启动、队列、后台初始化与消息任务的失败／关闭路径。"""
    await tester.test(_test_server_init_failure_still_cleans_up, "Server 初始化失败仍执行清理")
    await tester.test(_test_server_notices_dead_queue_poller, "Server 检测队列轮询异常退出")
    await tester.test(_test_server_keeps_queue_poller_alive_for_cleanup, "Server 清理期间保留队列轮询")
    await tester.test(_test_shutdown_cancels_background_initialization, "关闭时取消后台初始化")
    await tester.test(_test_background_init_cancels_failed_sibling, "后台初始化失败时取消同组任务")
    await tester.test(_test_remote_only_webrender_uses_remote_health, "remote_only 仅检查远端 WebRender")
    await tester.test(_test_background_init_uses_configured_webrender_health, "后台使用统一 WebRender 健康检查")
    await tester.test(_test_client_queue_poller_recovers_from_transient_failure, "客户端队列轮询异常后恢复")
    await tester.test(_test_message_background_failure_is_observed_and_cleaned, "消息后台异常被记录并清理")
    await tester.test(_test_shutdown_waits_for_inflight_queue_handlers, "关闭时等待在途队列处理器")
    await tester.test(_test_shutdown_prevents_new_queue_claims, "关闭期间停止领取新的队列任务")
    await tester.test(_test_background_cleanup_registry_is_generic_and_reload_safe, "后台清理注册与热重载替换")
    await tester.test(_test_background_cleanup_isolates_failure_and_timeout, "后台清理异常与超时隔离")
    await tester.test(
        _test_shutdown_cleanup_keeps_result_pump_without_new_claims,
        "后台清理期间 Queue 只回收结果",
    )
    await tester.test(
        _test_shutdown_runs_registered_cleanup_before_queue_stop,
        "关闭时执行注册后台清理再停止队列",
    )
    return tester
