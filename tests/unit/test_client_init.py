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
    with (
        patch.object(client_init_module, "init_db", new=AsyncMock(return_value=False)),
        patch.object(client_init_module.JobQueueClient, "send_keepalive_signal_to_server", new=keepalive),
    ):
        try:
            await client_init_module.client_init(queue=False, rename_logger=False)
        except RuntimeError as exc:
            return "Failed to initialize database" in str(exc) and keepalive.await_count == 0
    return False


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
    await tester.test(_test_slash_session_waits_for_initialization, "Slash 会话等待初始化完成")
    return tester
