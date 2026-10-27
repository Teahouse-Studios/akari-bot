"""各平台撤回事件转换测试。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from bots.discord import events as discord_events
from bots.kook import events as kook_events
from bots.matrix import events as matrix_events
from bots.milky import events as milky_events
from bots.onebot import events as onebot_events
from core.tester import Tester, func_case


async def _capture_event(module, callback, *args, **kwargs):
    event_info = SimpleNamespace()
    assign = AsyncMock(return_value=event_info)
    process = AsyncMock(return_value="task-id")
    with patch.object(module.EventInfo, "assign", new=assign), patch.object(module.Bot, "process_event", new=process):
        result = await callback(*args, **kwargs)

    process.assert_awaited_once_with(event_info)
    return result, assign.await_args.kwargs


def _event_matches(actual, expected) -> bool:
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(
            key in actual and _event_matches(actual[key], value) for key, value in expected.items()
        )
    return actual == expected


async def _test_onebot_group_recall():
    result, event = await _capture_event(
        onebot_events,
        onebot_events.message_recalled,
        456,
        222,
        group_id=123,
        operator_id=222,
    )
    return result == "task-id" and _event_matches(
        event,
        {
            "event_name": "message_recalled",
            "target_id": "QQ|Group|123",
            "target_from": "QQ|Group",
            "client_name": "QQ",
            "sender_id": "QQ|222",
            "sender_from": "QQ",
            "data": {"message_id": "456", "operator_id": "QQ|222"},
            "create": False,
        },
    )


async def _test_onebot_private_recall():
    result, event = await _capture_event(
        onebot_events,
        onebot_events.message_recalled,
        456,
        222,
    )
    return result == "task-id" and _event_matches(
        event,
        {
            "event_name": "message_recalled",
            "target_id": "QQ|Private|222",
            "target_from": "QQ|Private",
            "sender_id": "QQ|222",
            "data": {"message_id": "456"},
            "create": False,
        },
    )


async def _test_milky_group_recall():
    result, event = await _capture_event(
        milky_events,
        milky_events.message_recalled,
        456,
        222,
        group_id=123,
        operator_id=222,
    )
    return result == "task-id" and _event_matches(
        event,
        {
            "event_name": "message_recalled",
            "target_id": "QQ|Group|123",
            "target_from": "QQ|Group",
            "client_name": "QQ",
            "sender_id": "QQ|222",
            "data": {"message_id": "456", "operator_id": "QQ|222"},
            "create": False,
        },
    )


async def _test_discord_dm_recall():
    result, event = await _capture_event(
        discord_events,
        discord_events.message_recalled,
        456,
        123,
        "Discord|DM|Channel",
    )
    return result == "task-id" and _event_matches(
        event,
        {
            "event_name": "message_recalled",
            "target_id": "Discord|DM|Channel|123",
            "target_from": "Discord|DM|Channel",
            "client_name": "Discord",
            "data": {"message_id": "456"},
            "create": False,
        },
    )


async def _test_kook_group_recall():
    result, event = await _capture_event(
        kook_events,
        kook_events.message_recalled,
        456,
        222,
        group_id=123,
    )
    return result == "task-id" and _event_matches(
        event,
        {
            "event_name": "message_recalled",
            "target_id": "KOOK|Group|123",
            "target_from": "KOOK|Group",
            "client_name": "KOOK",
            "sender_id": "KOOK|User|222",
            "data": {"message_id": "456"},
            "create": False,
        },
    )


async def _test_kook_private_recall():
    result, event = await _capture_event(
        kook_events,
        kook_events.message_recalled,
        456,
        222,
    )
    return result == "task-id" and _event_matches(
        event,
        {
            "event_name": "message_recalled",
            "target_id": "KOOK|Person|222",
            "target_from": "KOOK|Person",
            "data": {"message_id": "456"},
            "create": False,
        },
    )


async def _test_matrix_redaction():
    result, event = await _capture_event(
        matrix_events,
        matrix_events.message_recalled,
        "$event-1",
        "!room-1",
        "Matrix|alice",
    )
    return result == "task-id" and _event_matches(
        event,
        {
            "event_name": "message_recalled",
            "target_id": "Matrix|Room|!room-1",
            "target_from": "Matrix|Room",
            "client_name": "Matrix",
            "sender_id": "Matrix|alice",
            "data": {"message_id": "$event-1", "operator_id": "Matrix|alice"},
            "create": False,
        },
    )


@func_case
async def test_platform_message_recall(tester: Tester):
    """各平台撤回通知被转换为统一的核心事件。"""
    await tester.test(_test_onebot_group_recall, "OneBot 群聊撤回事件转换")
    await tester.test(_test_onebot_private_recall, "OneBot 私聊撤回事件转换")
    await tester.test(_test_milky_group_recall, "Milky 群聊撤回事件转换")
    await tester.test(_test_discord_dm_recall, "Discord 私信删除事件转换")
    await tester.test(_test_kook_group_recall, "KOOK 群聊删除事件转换")
    await tester.test(_test_kook_private_recall, "KOOK 私聊删除事件转换")
    await tester.test(_test_matrix_redaction, "Matrix 撤回事件转换")
    return tester
