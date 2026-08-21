"""客户端初始化与 Discord 启动屏障单元测试。"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import bots.discord.client as discord_client
import bots.discord.slash_parser as discord_slash_parser
import core.client.init as client_init_module
from core.tester import Tester, func_case


async def _reset_discord_client_init_task() -> None:
    task = discord_client._client_init_task
    if task is not None and not task.done():
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    discord_client._client_init_task = None


async def _test_concurrent_discord_events_share_initialization():
    await _reset_discord_client_init_task()
    started = asyncio.Event()
    release = asyncio.Event()
    calls = 0

    async def initialize(*args, **kwargs):
        nonlocal calls
        calls += 1
        started.set()
        await release.wait()

    try:
        with patch.object(discord_client, "client_init", new=initialize):
            first = asyncio.create_task(discord_client.ensure_client_initialized())
            await asyncio.wait_for(started.wait(), timeout=1)
            second = asyncio.create_task(discord_client.ensure_client_initialized())
            await asyncio.sleep(0)
            both_waiting = not first.done() and not second.done()

            release.set()
            await asyncio.gather(first, second)
            await discord_client.ensure_client_initialized()

        return calls == 1 and both_waiting
    finally:
        await _reset_discord_client_init_task()


async def _test_failed_discord_initialization_can_retry():
    await _reset_discord_client_init_task()
    calls = 0

    async def initialize(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("first initialization failed")

    try:
        with patch.object(discord_client, "client_init", new=initialize):
            try:
                await discord_client.ensure_client_initialized()
            except RuntimeError:
                pass
            else:
                return False

            await discord_client.ensure_client_initialized()
            return calls == 2
    finally:
        await _reset_discord_client_init_task()


async def _test_database_failure_stops_client_initialization():
    keepalive = AsyncMock()
    close_db = AsyncMock()
    old_initialization_task = client_init_module._initialization_task
    client_init_module._initialization_task = None
    try:
        with (
            patch.object(client_init_module, "init_db", new=AsyncMock(return_value=False)),
            patch.object(client_init_module, "close_db", new=close_db),
            patch.object(client_init_module.JobQueueClient, "send_keepalive_signal_to_server", new=keepalive),
        ):
            try:
                await client_init_module.client_init(queue=False, rename_logger=False)
            except RuntimeError as exc:
                return (
                    "Failed to initialize database" in str(exc)
                    and keepalive.await_count == 0
                    and close_db.await_count == 1
                )
        return False
    finally:
        client_init_module._initialization_task = old_initialization_task


async def _test_database_failure_cleanup_allows_retry():
    old_queue_task = client_init_module._queue_task
    old_keepalive_task = client_init_module._keepalive_task
    old_initialization_task = client_init_module._initialization_task
    client_init_module._queue_task = None
    client_init_module._keepalive_task = None
    client_init_module._initialization_task = None
    init_db = AsyncMock(side_effect=[False, True])
    close_db = AsyncMock()
    keepalive = AsyncMock()
    keepalive_started = asyncio.Event()
    keepalive_release = asyncio.Event()

    async def keepalive_loop(*args, **kwargs):
        keepalive_started.set()
        await keepalive_release.wait()

    try:
        with (
            patch.object(client_init_module, "init_db", new=init_db),
            patch.object(client_init_module, "close_db", new=close_db),
            patch.object(client_init_module, "_keepalive_loop", new=keepalive_loop),
            patch.object(client_init_module.JobQueueClient, "send_keepalive_signal_to_server", new=keepalive),
            patch.object(client_init_module, "connect_locale_snapshot"),
            patch.object(client_init_module.Bot, "ContextSlots", [SimpleNamespace(features=SimpleNamespace())]),
            patch.object(client_init_module.Bot, "fetched_session_ctx_slot", 0),
        ):
            try:
                await client_init_module.client_init(queue=False, rename_logger=False)
            except RuntimeError:
                pass
            else:
                return False

            await client_init_module.client_init(queue=False, rename_logger=False)
            await asyncio.wait_for(keepalive_started.wait(), timeout=1)
            return init_db.await_count == 2 and close_db.await_count == 1 and keepalive.await_count == 1
    finally:
        keepalive_release.set()
        task = client_init_module._keepalive_task
        if task is not None and not task.done():
            task.cancel()
        if task is not None:
            await asyncio.gather(task, return_exceptions=True)
        client_init_module._queue_task = old_queue_task
        client_init_module._keepalive_task = old_keepalive_task
        client_init_module._initialization_task = old_initialization_task


async def _test_client_background_tasks_are_idempotent():
    queue_started = asyncio.Event()
    queue_release = asyncio.Event()

    async def queue_poller():
        queue_started.set()
        await queue_release.wait()

    old_queue_task = client_init_module._queue_task
    old_keepalive_task = client_init_module._keepalive_task
    old_initialization_task = client_init_module._initialization_task
    client_init_module._queue_task = None
    client_init_module._keepalive_task = None
    client_init_module._initialization_task = None
    init_db = AsyncMock(return_value=True)
    try:
        with (
            patch.object(client_init_module, "init_db", new=init_db),
            patch.object(client_init_module, "check_queue", new=queue_poller),
            patch.object(
                client_init_module.JobQueueClient,
                "send_keepalive_signal_to_server",
                new=AsyncMock(),
            ),
            patch.object(client_init_module.Bot, "ContextSlots", [SimpleNamespace(features=SimpleNamespace())]),
            patch.object(client_init_module.Bot, "fetched_session_ctx_slot", 0),
        ):
            await client_init_module.client_init(rename_logger=False)
            await asyncio.wait_for(queue_started.wait(), timeout=1)
            first_queue_task = client_init_module._queue_task
            first_keepalive_task = client_init_module._keepalive_task

            await client_init_module.client_init(rename_logger=False)
            return (
                first_queue_task is client_init_module._queue_task
                and first_keepalive_task is client_init_module._keepalive_task
                and init_db.await_count == 1
                and init_db.await_args.kwargs == {"load_module_db": False, "generate_schemas": False}
            )
    finally:
        queue_release.set()
        tasks = [client_init_module._queue_task, client_init_module._keepalive_task]
        for task in tasks:
            if task is not None and not task.done():
                task.cancel()
        await asyncio.gather(*(task for task in tasks if task is not None), return_exceptions=True)
        client_init_module._queue_task = old_queue_task
        client_init_module._keepalive_task = old_keepalive_task
        client_init_module._initialization_task = old_initialization_task


async def _test_slash_session_waits_for_initialization():
    started = asyncio.Event()
    release = asyncio.Event()
    assigned = SimpleNamespace()
    assign = AsyncMock(return_value=assigned)

    class FakeApplicationContext:
        channel = SimpleNamespace(id=20)
        author = SimpleNamespace(id=1, name="tester")
        command = SimpleNamespace(id=30, __str__=lambda self: "wiki")

    async def wait_for_initialization():
        started.set()
        await release.wait()

    with (
        patch.object(discord_slash_parser.discord, "ApplicationContext", FakeApplicationContext),
        patch.object(discord_slash_parser, "ensure_client_initialized", new=wait_for_initialization),
        patch.object(discord_slash_parser.SessionInfo, "assign", new=assign),
    ):
        task = asyncio.create_task(discord_slash_parser.ctx_to_session(FakeApplicationContext(), "search"))
        await asyncio.wait_for(started.wait(), timeout=1)
        assign_blocked = assign.await_count == 0 and not task.done()
        release.set()
        result = await task

    return assign_blocked and result is assigned and assign.await_count == 1


@func_case
async def test_client_init(tester: Tester):
    """客户端初始化只执行一次，并阻止 Discord 事件抢跑。"""
    await tester.test(_test_concurrent_discord_events_share_initialization, "并发事件共享初始化任务")
    await tester.test(_test_failed_discord_initialization_can_retry, "初始化失败后允许重试")
    await tester.test(_test_database_failure_stops_client_initialization, "数据库失败时停止客户端初始化")
    await tester.test(_test_database_failure_cleanup_allows_retry, "数据库失败清理后允许重试")
    await tester.test(_test_client_background_tasks_are_idempotent, "客户端后台任务幂等")
    await tester.test(_test_slash_session_waits_for_initialization, "Slash 会话等待初始化完成")
    return tester
