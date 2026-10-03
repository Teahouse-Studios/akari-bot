import asyncio
from collections import OrderedDict
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from botpy.message import C2CMessage, DirectMessage, GroupMessage, Message

from bots.qqbot.config import QQBotConfig
from core.tester import Tester, func_case

with patch.object(QQBotConfig, "enable", False):
    import bots.qqbot.bot as qqbot_bot


def _message(message_id="source", target="group", content="~ping", scope="group"):
    data = {
        "id": message_id,
        "group_openid": target,
        "guild_id": "guild",
        "channel_id": "channel",
        "author": {
            "member_openid": "sender",
            "id": "sender",
            "user_openid": "sender",
            "username": "sender",
            "member_role": "member",
        },
        "content": content,
    }
    message_type = {"group": GroupMessage, "channel": Message, "dm": DirectMessage, "c2c": C2CMessage}[scope]
    return message_type(None, "event", data)


async def _dispatch(events):
    assign = AsyncMock(side_effect=lambda **kwargs: SimpleNamespace(**kwargs))
    process = AsyncMock()
    with (
        patch.object(qqbot_bot.SessionInfo, "assign", assign),
        patch.object(qqbot_bot.Bot, "process_message", process),
        patch.object(qqbot_bot, "resolve_features", return_value=SimpleNamespace()),
        patch.object(qqbot_bot, "cache_permission"),
        patch.object(qqbot_bot, "_inbound_message_cache", OrderedDict()),
    ):
        for handler, message in events:
            await handler(message)
    return assign, process


async def _test_group_message_redelivery_is_processed_once():
    handler = qqbot_bot.MyClient.on_message_group_create
    assign, process = await _dispatch([(handler, _message("redelivered")), (handler, _message("redelivered"))])
    assert assign.await_count == process.await_count == 1
    return True


async def _test_group_message_and_at_callbacks_share_identity():
    ordinary = _message("overlapping")
    mentioned = _message("overlapping")
    mentioned.event_id = "another-event"
    assign, process = await _dispatch(
        [
            (qqbot_bot.MyClient.on_message_group_create, ordinary),
            (qqbot_bot.MyClient.on_group_at_message_create, mentioned),
        ]
    )
    assert assign.await_count == process.await_count == 1
    return True


async def _test_concurrent_callbacks_are_claimed_before_await():
    handler = qqbot_bot.MyClient.on_message_group_create
    assign_started = asyncio.Event()
    assign_release = asyncio.Event()

    async def assign(**kwargs):
        assign_started.set()
        await assign_release.wait()
        return SimpleNamespace(**kwargs)

    process = AsyncMock()
    assign_mock = AsyncMock(side_effect=assign)
    with (
        patch.object(qqbot_bot, "_inbound_message_cache", OrderedDict()),
        patch.object(qqbot_bot.SessionInfo, "assign", assign_mock),
        patch.object(qqbot_bot.Bot, "process_message", process),
        patch.object(qqbot_bot, "resolve_features", return_value=SimpleNamespace()),
        patch.object(qqbot_bot, "cache_permission"),
    ):
        first = asyncio.create_task(handler(_message("concurrent")))
        try:
            await assign_started.wait()
            await qqbot_bot.MyClient.on_group_at_message_create(_message("concurrent"))
        finally:
            assign_release.set()
            await first
        assert assign_mock.await_count == process.await_count == 1
    return True


async def _test_distinct_messages_and_targets_are_preserved():
    handler = qqbot_bot.MyClient.on_message_group_create
    assign, process = await _dispatch(
        [(handler, _message("one")), (handler, _message("two")), (handler, _message("one", "another-group"))]
    )
    assert assign.await_count == process.await_count == 3
    return True


async def _test_failed_callback_can_be_redelivered():
    for error in (RuntimeError("session unavailable"), asyncio.CancelledError()):
        process = AsyncMock()
        assign = AsyncMock(side_effect=[error, SimpleNamespace()])
        with (
            patch.object(qqbot_bot, "_inbound_message_cache", OrderedDict()),
            patch.object(qqbot_bot.SessionInfo, "assign", assign),
            patch.object(qqbot_bot.Bot, "process_message", process),
            patch.object(qqbot_bot, "resolve_features", return_value=SimpleNamespace()),
            patch.object(qqbot_bot, "cache_permission"),
        ):
            handler = qqbot_bot.MyClient.on_message_group_create
            try:
                await handler(_message("failed"))
            except (RuntimeError, asyncio.CancelledError) as raised:
                assert raised is error
            else:
                raise AssertionError("The callback failure must propagate")
            await handler(_message("failed"))
            assert assign.await_count == 2 and process.await_count == 1
    return True


async def _test_other_message_callbacks_share_deduplication():
    for handler, scope in (
        (qqbot_bot.MyClient.on_at_message_create, "channel"),
        (qqbot_bot.MyClient.on_message_create, "channel"),
        (qqbot_bot.MyClient.on_group_at_message_create, "group"),
        (qqbot_bot.MyClient.on_direct_message_create, "dm"),
        (qqbot_bot.MyClient.on_c2c_message_create, "c2c"),
    ):
        assign, process = await _dispatch([(handler, _message(scope=scope)), (handler, _message(scope=scope))])
        assert assign.await_count == process.await_count == 1
    assign, process = await _dispatch(
        [
            (qqbot_bot.MyClient.on_message_create, _message(scope="channel")),
            (qqbot_bot.MyClient.on_at_message_create, _message(scope="channel")),
        ]
    )
    assert assign.await_count == process.await_count == 1
    return True


async def _test_cache_expires_and_stays_bounded():
    observed = []

    @qqbot_bot._deduplicate_message
    async def handler(message):
        observed.append(message.id)

    cache = OrderedDict()
    with (
        patch.object(qqbot_bot, "_inbound_message_cache", cache),
        patch.object(qqbot_bot, "INBOUND_MESSAGE_CACHE_MAX_SIZE", 2),
        patch.object(qqbot_bot.time, "monotonic", side_effect=[0, 5, 6, 7, 301, 307]),
    ):
        for message_id in ("one", "one", "two", "three", "three", "four"):
            await handler(_message(message_id))
            assert len(cache) <= 2
        assert observed == ["one", "two", "three", "four"]
        assert list(cache.values()) == [307]
    return True


async def _test_unidentified_messages_are_not_suppressed():
    handler = qqbot_bot.MyClient.on_message_group_create
    assign, process = await _dispatch([(handler, _message(None)), (handler, _message(None))])
    assert assign.await_count == process.await_count == 2
    return True


async def _test_mention_prefix_survives_overlapping_callbacks():
    for handlers in (
        (qqbot_bot.MyClient.on_message_group_create, qqbot_bot.MyClient.on_group_at_message_create),
        (qqbot_bot.MyClient.on_group_at_message_create, qqbot_bot.MyClient.on_message_group_create),
    ):
        with patch.object(qqbot_bot, "qqbot_openid", "bot"):
            assign, process = await _dispatch([(handler, _message(content="<@bot> /ping")) for handler in handlers])
        assert assign.await_count == process.await_count == 1
        assert assign.await_args.kwargs["prefixes"] == ["/"]
        assert assign.await_args.kwargs["messages"].to_str() == "/ping"
    return True


@func_case
async def test_qqbot_delivery(tester: Tester):
    await tester.test(_test_group_message_redelivery_is_processed_once, "同一群消息重投只派发一次")
    await tester.test(_test_group_message_and_at_callbacks_share_identity, "普通群消息与提及回调共用消息身份")
    await tester.test(_test_concurrent_callbacks_are_claimed_before_await, "并发回调在等待会话创建前认领消息")
    await tester.test(_test_distinct_messages_and_targets_are_preserved, "同文本不同消息及不同目标均可派发")
    await tester.test(_test_failed_callback_can_be_redelivered, "回调失败或取消后允许重投")
    await tester.test(_test_other_message_callbacks_share_deduplication, "频道、私信及单聊回调共用去重边界")
    await tester.test(_test_cache_expires_and_stays_bounded, "入站去重缓存过期与容量限制")
    await tester.test(_test_unidentified_messages_are_not_suppressed, "缺少消息 ID 的事件不合并")
    await tester.test(_test_mention_prefix_survives_overlapping_callbacks, "普通与提及回调顺序不影响群提及命令前缀")
    return tester
