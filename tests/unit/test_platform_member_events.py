"""各平台成员加入事件转换测试。"""

import json
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from bots.discord import events as discord_events
from bots.kook import events as kook_events
from bots.matrix import events as matrix_events
from bots.telegram import events as telegram_events
from core.tester import Tester, func_case


async def _capture_event(module, callback, *args, **kwargs):
    event_info = SimpleNamespace()
    assign = AsyncMock(return_value=event_info)
    process = AsyncMock(return_value="task-id")
    with patch.object(module.EventInfo, "assign", new=assign), patch.object(module.Bot, "process_event", new=process):
        result = await callback(*args, **kwargs)

    process.assert_awaited_once_with(event_info)
    return result, assign.await_args.kwargs


async def _test_discord_guild_member_joined():
    joined_at = datetime(2026, 8, 18, 12, 0, tzinfo=UTC)
    result, event = await _capture_event(
        discord_events,
        discord_events.guild_member_joined,
        "user-1",
        "guild-1",
        joined_at,
    )
    json.dumps(event["data"])
    return result == "task-id" and event == {
        "event_name": "guild_member_joined",
        "target_id": "Discord|Guild|guild-1",
        "target_from": "Discord|Guild",
        "client_name": "Discord",
        "sender_id": "Discord|Client|user-1",
        "sender_from": "Discord|Client",
        "data": {"joined_at": joined_at.isoformat()},
    }


async def _test_discord_guild_member_left():
    result, event = await _capture_event(
        discord_events,
        discord_events.guild_member_left,
        "user-1",
        "guild-1",
    )
    return result == "task-id" and event == {
        "event_name": "guild_member_left",
        "target_id": "Discord|Guild|guild-1",
        "target_from": "Discord|Guild",
        "client_name": "Discord",
        "sender_id": "Discord|Client|user-1",
        "sender_from": "Discord|Client",
    }


async def _test_telegram_group_members_joined():
    joined_at = datetime(2026, 8, 18, 12, 1, tzinfo=UTC)
    message = SimpleNamespace(
        chat=SimpleNamespace(type="supergroup", id=-10001),
        new_chat_members=[SimpleNamespace(id=1), SimpleNamespace(id=2), SimpleNamespace(id=3)],
        date=joined_at,
        message_id=101,
    )
    dispatch = AsyncMock()
    with patch.object(telegram_events, "member_joined", new=dispatch):
        await telegram_events.handle_new_chat_members(message, bot_id=2, ignored_sender=["Telegram|User|3"])

    dispatch.assert_awaited_once_with(
        1,
        -10001,
        "supergroup",
        joined_at=joined_at,
        message_id=101,
    )

    result, event = await _capture_event(
        telegram_events,
        telegram_events.member_joined,
        1,
        -10001,
        "supergroup",
        joined_at,
        101,
    )
    json.dumps(event["data"])
    return result == "task-id" and event == {
        "event_name": "member_joined",
        "target_id": "Telegram|Supergroup|-10001",
        "target_from": "Telegram|Supergroup",
        "client_name": "Telegram",
        "sender_id": "Telegram|User|1",
        "sender_from": "Telegram|User",
        "data": {"joined_at": joined_at.isoformat(), "message_id": "101"},
    }


async def _test_telegram_group_member_left():
    left_at = datetime(2026, 8, 18, 12, 2, tzinfo=UTC)
    message = SimpleNamespace(
        chat=SimpleNamespace(type="group", id=-10002),
        left_chat_member=SimpleNamespace(id=4),
        date=left_at,
        message_id=102,
    )
    dispatch = AsyncMock()
    with patch.object(telegram_events, "member_left", new=dispatch):
        await telegram_events.handle_left_chat_member(message, bot_id=2, ignored_sender=[])

    dispatch.assert_awaited_once_with(
        4,
        -10002,
        "group",
        left_at=left_at,
        message_id=102,
    )

    result, event = await _capture_event(
        telegram_events,
        telegram_events.member_left,
        4,
        -10002,
        "group",
        left_at,
        102,
    )
    json.dumps(event["data"])
    return result == "task-id" and event == {
        "event_name": "member_left",
        "target_id": "Telegram|Group|-10002",
        "target_from": "Telegram|Group",
        "client_name": "Telegram",
        "sender_id": "Telegram|User|4",
        "sender_from": "Telegram|User",
        "data": {"left_at": left_at.isoformat(), "message_id": "102"},
    }


async def _test_kook_guild_member_joined():
    result, event = await _capture_event(
        kook_events,
        kook_events.guild_member_joined,
        "user-2",
        "guild-2",
        1787040000000,
        "event-2",
    )
    json.dumps(event["data"])
    return result == "task-id" and event == {
        "event_name": "guild_member_joined",
        "target_id": "KOOK|Guild|guild-2",
        "target_from": "KOOK|Guild",
        "client_name": "KOOK",
        "sender_id": "KOOK|User|user-2",
        "sender_from": "KOOK|User",
        "data": {"joined_at": 1787040000000, "event_id": "event-2"},
    }


async def _test_kook_guild_member_left():
    result, event = await _capture_event(
        kook_events,
        kook_events.guild_member_left,
        "user-2",
        "guild-2",
        1787040001000,
        "event-4",
    )
    json.dumps(event["data"])
    return result == "task-id" and event == {
        "event_name": "guild_member_left",
        "target_id": "KOOK|Guild|guild-2",
        "target_from": "KOOK|Guild",
        "client_name": "KOOK",
        "sender_id": "KOOK|User|user-2",
        "sender_from": "KOOK|User",
        "data": {"left_at": 1787040001000, "event_id": "event-4"},
    }


async def _test_matrix_room_member_joined():
    sender_id = "Matrix|alice:example.org"
    predicate_args = {
        "member_id": "@alice:example.org",
        "bot_id": "@bot:example.org",
        "membership": "join",
        "prev_membership": "invite",
        "sender_id": sender_id,
        "ignored_sender": [],
    }
    if matrix_events.should_dispatch_member_joined(initial_sync_complete=False, **predicate_args):
        return False
    if not matrix_events.should_dispatch_member_joined(initial_sync_complete=True, **predicate_args):
        return False
    if matrix_events.should_dispatch_member_joined(
        initial_sync_complete=True,
        **(predicate_args | {"prev_membership": "join"}),
    ):
        return False

    result, event = await _capture_event(
        matrix_events,
        matrix_events.member_joined,
        "@alice:example.org",
        "!room:example.org",
        "event-3",
    )
    json.dumps(event["data"])
    return result == "task-id" and event == {
        "event_name": "member_joined",
        "target_id": "Matrix|Room|!room:example.org",
        "target_from": "Matrix|Room",
        "client_name": "Matrix",
        "sender_id": sender_id,
        "sender_from": "Matrix",
        "data": {"event_id": "event-3"},
    }


async def _test_matrix_room_member_left():
    sender_id = "Matrix|alice:example.org"
    predicate_args = {
        "member_id": "@alice:example.org",
        "bot_id": "@bot:example.org",
        "prev_membership": "join",
        "sender_id": sender_id,
        "ignored_sender": [],
    }
    if matrix_events.should_dispatch_member_left(
        initial_sync_complete=False,
        membership="leave",
        **predicate_args,
    ):
        return False
    if not matrix_events.should_dispatch_member_left(
        initial_sync_complete=True,
        membership="leave",
        **predicate_args,
    ):
        return False
    if not matrix_events.should_dispatch_member_left(
        initial_sync_complete=True,
        membership="ban",
        **predicate_args,
    ):
        return False
    if matrix_events.should_dispatch_member_left(
        initial_sync_complete=True,
        membership="leave",
        **(predicate_args | {"prev_membership": "invite"}),
    ):
        return False

    result, event = await _capture_event(
        matrix_events,
        matrix_events.member_left,
        "@alice:example.org",
        "!room:example.org",
        "event-5",
    )
    json.dumps(event["data"])
    return result == "task-id" and event == {
        "event_name": "member_left",
        "target_id": "Matrix|Room|!room:example.org",
        "target_from": "Matrix|Room",
        "client_name": "Matrix",
        "sender_id": sender_id,
        "sender_from": "Matrix",
        "data": {"event_id": "event-5"},
    }


@func_case
async def test_platform_member_events(tester: Tester):
    await tester.test(_test_discord_guild_member_joined, "Discord 服务器成员加入事件转换测试")
    await tester.test(_test_discord_guild_member_left, "Discord 服务器成员离开事件转换测试")
    await tester.test(_test_telegram_group_members_joined, "Telegram 群组成员加入事件转换测试")
    await tester.test(_test_telegram_group_member_left, "Telegram 群组成员离开事件转换测试")
    await tester.test(_test_kook_guild_member_joined, "KOOK 服务器成员加入事件转换测试")
    await tester.test(_test_kook_guild_member_left, "KOOK 服务器成员离开事件转换测试")
    await tester.test(_test_matrix_room_member_joined, "Matrix 房间成员加入事件转换测试")
    await tester.test(_test_matrix_room_member_left, "Matrix 房间成员离开事件转换测试")
    return tester
