"""平台适配器的长期缓存、主动推送队列与输入状态生命周期测试。"""

import asyncio
import importlib
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import patch

import bots.onebot.context as onebot_context
import bots.qqbot.context as qqbot_context
from bots.discord.context import DiscordContextManager
from bots.discord.slash_context import DiscordSlashContextManager
from bots.web.config import WebConfig
from bots.web.context import WebContextManager
from core.builtins.temp import Temp
from core.tester import Tester, func_case
from fastapi import WebSocketDisconnect


def _fake_post_session(target_id: str = "Test|Group|1", high_priority: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        target_id=target_id,
        target_union_info=SimpleNamespace(target_data={"in_post_whitelist": high_priority}),
    )


def _test_onebot_typing_cache_is_bounded_and_expires() -> bool:
    onebot_context.last_send_typing_time.clear()
    try:
        for index in range(onebot_context.TYPING_CACHE_MAX_SIZE + 10):
            onebot_context._record_typing_prompt(str(index), now=float(index))
        bounded = len(onebot_context.last_send_typing_time) == onebot_context.TYPING_CACHE_MAX_SIZE
        expired = not onebot_context._typing_prompt_on_cooldown(
            str(onebot_context.TYPING_CACHE_MAX_SIZE + 9),
            now=float(onebot_context.TYPING_CACHE_MAX_SIZE + 9 + onebot_context.TYPING_CACHE_TTL + 1),
        )
        return bounded and expired and not onebot_context.last_send_typing_time
    finally:
        onebot_context.last_send_typing_time.clear()


def _test_qqbot_permission_cache_is_safe_and_bounded() -> bool:
    qqbot_context.permission_cache.clear()
    try:
        qqbot_context.cache_permission("ordinary", False, now=0)
        if qqbot_context.permission_cache:
            return False
        for index in range(qqbot_context.PERMISSION_CACHE_MAX_SIZE + 10):
            qqbot_context.cache_permission(str(index), True, now=float(index))
        newest = str(qqbot_context.PERMISSION_CACHE_MAX_SIZE + 9)
        return (
            len(qqbot_context.permission_cache) == qqbot_context.PERMISSION_CACHE_MAX_SIZE
            and qqbot_context.get_cached_permission(newest, now=float(qqbot_context.PERMISSION_CACHE_MAX_SIZE + 9))
            and not qqbot_context.get_cached_permission(
                newest,
                now=float(qqbot_context.PERMISSION_CACHE_MAX_SIZE + 9 + qqbot_context.PERMISSION_CACHE_TTL + 1),
            )
        )
    finally:
        qqbot_context.permission_cache.clear()


def _test_telegram_imports_stay_in_platform_process() -> bool:
    config_probe = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import bots.telegram.config; "
            "assert not any(name == 'aiogram' or name.startswith('aiogram.') for name in sys.modules)",
        ],
        capture_output=True,
        timeout=30,
        check=False,
    )
    builder_probe = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import bots.telegram.message_builder; assert 'core.utils.web_render' not in sys.modules",
        ],
        capture_output=True,
        timeout=30,
        check=False,
    )
    return config_probe.returncode == 0 and builder_probe.returncode == 0


def _test_initiative_queue_fairness() -> bool:
    onebot_context._tasks_high_priority.clear()
    onebot_context._tasks.clear()
    onebot_context.OneBotFetchedContextManager._high_priority_count = 0
    try:
        onebot_context._tasks_high_priority.extend((f"high-{index}",) for index in range(6))
        onebot_context._tasks.append(("normal",))
        selected = [onebot_context.OneBotFetchedContextManager._take_next_task() for _ in range(6)]
        return [high_priority for _, high_priority in selected] == [True, True, True, True, True, False]
    finally:
        onebot_context._tasks_high_priority.clear()
        onebot_context._tasks.clear()
        onebot_context.OneBotFetchedContextManager._high_priority_count = 0


async def _test_initiative_queue_capacity_and_cancel_cleanup() -> bool:
    onebot_context._tasks_high_priority.clear()
    onebot_context._tasks.clear()
    try:
        onebot_context._tasks.extend((None,) for _ in range(onebot_context.INITIATIVE_QUEUE_MAX_SIZE))
        overflow = await onebot_context.OneBotFetchedContextManager.send_message(_fake_post_session(), None)
        if overflow != [] or len(onebot_context._tasks) != onebot_context.INITIATIVE_QUEUE_MAX_SIZE:
            return False

        onebot_context._tasks.clear()
        waiting = asyncio.create_task(
            onebot_context.OneBotFetchedContextManager.send_message(_fake_post_session(), None)
        )
        await asyncio.sleep(0)
        waiting.cancel()
        await asyncio.gather(waiting, return_exceptions=True)
        return not onebot_context._tasks and not onebot_context._tasks_high_priority
    finally:
        onebot_context._tasks_high_priority.clear()
        onebot_context._tasks.clear()


async def _test_high_priority_queue_keeps_reserved_capacity() -> bool:
    onebot_context._tasks_high_priority.clear()
    onebot_context._tasks.clear()
    loop = asyncio.get_running_loop()
    queued_futures = []
    try:
        for _ in range(onebot_context.INITIATIVE_QUEUE_MAX_SIZE):
            future = loop.create_future()
            queued_futures.append(future)
            onebot_context._tasks.append((future, _fake_post_session(), None, True, True, True))

        high_priority = asyncio.create_task(
            onebot_context.OneBotFetchedContextManager.send_message(
                _fake_post_session(high_priority=True),
                None,
            )
        )
        await asyncio.sleep(0)
        admitted = len(onebot_context._tasks_high_priority) == 1 and queued_futures[0].result() == []
        high_priority.cancel()
        await asyncio.gather(high_priority, return_exceptions=True)
        return admitted and len(onebot_context._tasks) == onebot_context.INITIATIVE_QUEUE_MAX_SIZE - 1
    finally:
        for future in queued_futures:
            if not future.done():
                future.cancel()
        onebot_context._tasks_high_priority.clear()
        onebot_context._tasks.clear()


async def _stop_initiative_worker(context_module, manager) -> bool:
    if not hasattr(manager, "stop_task_processor"):
        return False

    context_module._tasks_high_priority.clear()
    context_module._tasks.clear()
    release = asyncio.Event()

    async def idle_worker():
        await release.wait()

    worker = asyncio.create_task(idle_worker())
    manager._processor_task = worker
    waiting = asyncio.create_task(manager.send_message(_fake_post_session(), None))
    await asyncio.sleep(0)
    try:
        await manager.stop_task_processor()
        result = await asyncio.wait_for(waiting, timeout=1)
        return (
            result == []
            and worker.cancelled()
            and manager._processor_task is None
            and not context_module._tasks
            and not context_module._tasks_high_priority
        )
    finally:
        release.set()
        if not worker.done():
            worker.cancel()
        if not waiting.done():
            waiting.cancel()
        await asyncio.gather(worker, waiting, return_exceptions=True)
        manager._processor_task = None
        context_module._tasks_high_priority.clear()
        context_module._tasks.clear()


async def _test_initiative_workers_stop_and_release_waiters() -> bool:
    onebot_stopped = await _stop_initiative_worker(
        onebot_context,
        onebot_context.OneBotFetchedContextManager,
    )
    qqbot_stopped = await _stop_initiative_worker(
        qqbot_context,
        qqbot_context.QQBotFetchedContextManager,
    )
    return onebot_stopped and qqbot_stopped


async def _test_onebot_typing_end_cannot_miss_registration() -> bool:
    session = SimpleNamespace(session_id="onebot-typing-race", target_from="private")
    onebot_context.OneBotContextManager.context[session.session_id] = object()
    try:
        await onebot_context.OneBotContextManager.start_typing(session)
        await onebot_context.OneBotContextManager.end_typing(session)
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        return (
            session.session_id not in onebot_context.OneBotContextManager.typing_flags
            and session.session_id not in onebot_context.OneBotContextManager.typing_tasks
        )
    finally:
        onebot_context.OneBotContextManager.context.pop(session.session_id, None)
        onebot_context.OneBotContextManager.typing_flags.pop(session.session_id, None)
        task = onebot_context.OneBotContextManager.typing_tasks.pop(session.session_id, None)
        if task:
            task.cancel()


async def _test_web_typing_end_cannot_miss_registration() -> bool:
    session = SimpleNamespace(session_id="web-typing-race", message_id="1")
    WebContextManager.context[session.session_id] = {"message": "hello"}

    class _FakeWebSocket:
        def __init__(self):
            self.statuses = []

        async def send_text(self, payload: str):
            self.statuses.append(payload)

    websocket = _FakeWebSocket()
    previous_websocket = Temp.data.get("web_chat_websocket")
    Temp.data["web_chat_websocket"] = websocket
    WebContextManager.context[session.session_id]["websocket"] = websocket
    try:
        await WebContextManager.start_typing(session)
        await WebContextManager.end_typing(session)
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        cleaned = (
            session.session_id not in WebContextManager.typing_flags
            and session.session_id not in WebContextManager.typing_tasks
        )
        return cleaned and not any('"status":"start"' in payload for payload in websocket.statuses)
    finally:
        if previous_websocket is None:
            Temp.data.pop("web_chat_websocket", None)
        else:
            Temp.data["web_chat_websocket"] = previous_websocket
        WebContextManager.context.pop(session.session_id, None)
        WebContextManager.typing_flags.pop(session.session_id, None)
        task = WebContextManager.typing_tasks.pop(session.session_id, None)
        if task:
            task.cancel()


class _FakeTypingContext:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False


async def _test_discord_slash_typing_end_cannot_miss_registration() -> bool:
    session = SimpleNamespace(session_id="discord-typing-race")
    deferred = []

    async def defer():
        deferred.append(True)

    ctx = SimpleNamespace(
        channel=SimpleNamespace(typing=lambda: _FakeTypingContext()),
        defer=defer,
    )
    DiscordSlashContextManager.context[session.session_id] = ctx
    try:
        await DiscordSlashContextManager.start_typing(session)
        await DiscordSlashContextManager.end_typing(session)
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        return (
            session.session_id not in DiscordSlashContextManager.typing_flags
            and session.session_id not in DiscordSlashContextManager.typing_tasks
            and not deferred
        )
    finally:
        DiscordSlashContextManager.context.pop(session.session_id, None)
        DiscordSlashContextManager.typing_flags.pop(session.session_id, None)
        task = DiscordSlashContextManager.typing_tasks.pop(session.session_id, None)
        if task:
            task.cancel()


async def _test_web_disconnect_keeps_newer_websocket() -> bool:
    with patch.object(WebConfig, "enable", False, create=True):
        web_bot = importlib.import_module("bots.web.bot")

    class _FakeWebSocket:
        def __init__(self):
            self.accepted = asyncio.Event()
            self.disconnect = asyncio.Event()

        async def accept(self):
            self.accepted.set()

        async def receive_text(self):
            await self.disconnect.wait()
            raise WebSocketDisconnect(code=1000)

        async def close(self):
            return None

    first = _FakeWebSocket()
    second = _FakeWebSocket()
    previous_websocket = Temp.data.get("web_chat_websocket")
    first_task = asyncio.create_task(web_bot.websocket_chat(first))
    second_task = None
    try:
        await asyncio.wait_for(first.accepted.wait(), timeout=1)
        if Temp.data.get("web_chat_websocket") is not first:
            return False

        second_task = asyncio.create_task(web_bot.websocket_chat(second))
        await asyncio.wait_for(second.accepted.wait(), timeout=1)
        if Temp.data.get("web_chat_websocket") is not second:
            return False

        first.disconnect.set()
        await asyncio.wait_for(first_task, timeout=1)
        return Temp.data.get("web_chat_websocket") is second
    finally:
        first.disconnect.set()
        second.disconnect.set()
        tasks = [first_task]
        if second_task:
            tasks.append(second_task)
        await asyncio.gather(*tasks, return_exceptions=True)
        if previous_websocket is None:
            Temp.data.pop("web_chat_websocket", None)
        else:
            Temp.data["web_chat_websocket"] = previous_websocket


async def _test_discord_typing_end_cannot_miss_registration() -> bool:
    if not hasattr(DiscordContextManager, "typing_tasks"):
        return False

    session = SimpleNamespace(session_id="discord-typing-race")
    entered = asyncio.Event()
    exited = asyncio.Event()

    class _TypingContext:
        async def __aenter__(self):
            entered.set()
            return self

        async def __aexit__(self, *exc_info):
            exited.set()
            return False

    ctx = SimpleNamespace(channel=SimpleNamespace(typing=lambda: _TypingContext()))
    DiscordContextManager.context[session.session_id] = ctx
    try:
        await DiscordContextManager.start_typing(session)
        await asyncio.wait_for(entered.wait(), timeout=1)
        await DiscordContextManager.end_typing(session)
        await asyncio.wait_for(exited.wait(), timeout=1)
        return (
            session.session_id not in DiscordContextManager.typing_flags
            and session.session_id not in DiscordContextManager.typing_tasks
        )
    finally:
        DiscordContextManager.context.pop(session.session_id, None)
        DiscordContextManager.typing_flags.pop(session.session_id, None)
        task = DiscordContextManager.typing_tasks.pop(session.session_id, None)
        if task:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


@func_case
async def test_platform_memory(tester: Tester):
    """平台侧长期运行内存的有界性与清理路径。"""
    await tester.test(_test_onebot_typing_cache_is_bounded_and_expires, "OneBot typing 缓存有界并过期")
    await tester.test(_test_qqbot_permission_cache_is_safe_and_bounded, "QQBot 权限缓存安全且有界")
    await tester.test(_test_initiative_queue_fairness, "主动推送队列公平调度")
    await tester.test(_test_initiative_queue_capacity_and_cancel_cleanup, "主动推送队列容量与取消清理")
    await tester.test(_test_high_priority_queue_keeps_reserved_capacity, "主动推送高优先级保留容量")
    await tester.test(_test_initiative_workers_stop_and_release_waiters, "主动推送 worker 关闭并释放等待者")
    await tester.test(_test_onebot_typing_end_cannot_miss_registration, "OneBot typing 注册竞态")
    await tester.test(_test_web_typing_end_cannot_miss_registration, "Web typing 注册竞态")
    await tester.test(_test_web_disconnect_keeps_newer_websocket, "Web 旧连接断开不清除新连接")
    await tester.test(_test_discord_typing_end_cannot_miss_registration, "Discord typing 注册竞态")
    await tester.test(_test_discord_slash_typing_end_cannot_miss_registration, "Discord Slash typing 注册竞态")
    await tester.test(_test_telegram_imports_stay_in_platform_process, "Telegram 重依赖保持平台进程隔离")
    return tester
