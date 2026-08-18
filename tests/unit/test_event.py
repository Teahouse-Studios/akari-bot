"""模块事件注册、事件上下文及跨进程分发单元测试。"""

from types import SimpleNamespace
from typing import Literal, get_args, get_origin, get_type_hints
from unittest.mock import AsyncMock, patch

from core.builtins.bot import Bot
from core.builtins.converter import converter
from core.builtins.session.info import EventInfo
from core.component import Bind
from core.database.models import SenderUnionInfo, TargetUnionInfo
from core.loader import ModulesManager
from core.queue.client import JobQueueClient
from core.queue.server import JobQueueServer
from core.tester import Tester, func_case
from core.types import Module


def _remove_test_module(module_name: str):
    ModulesManager.modules.pop(module_name, None)
    ModulesManager.modules_origin.pop(module_name, None)
    ModulesManager.refresh()


def _test_event_binding():
    module_name = "__test_event_binding"
    try:
        module = Module.assign(module_name=module_name, alias=None, recommend_modules=None, developers=None, event=True)
        ModulesManager.add_module(module, "test.py")

        async def handler(event):
            return event

        Bind.Module(module_name).event("ready", available_for="QQBot|Group")(handler)
        events = ModulesManager.modules[module_name].events_list.set
        return (
            len(events) == 1
            and events[0].name == "ready"
            and events[0].function is handler
            and events[0].available_for == ["QQBot|Group"]
        )
    finally:
        _remove_test_module(module_name)


async def _test_event_name_literal_hint():
    annotation = get_type_hints(EventInfo)["event_name"]
    literal_type = next((arg for arg in get_args(annotation) if get_origin(arg) is Literal), None)
    custom_event = await EventInfo.assign(event_name="custom_module_event")
    return (
        literal_type is not None
        and set(get_args(literal_type))
        == {
            "member_joined",
            "member_left",
            "guild_member_joined",
            "guild_member_left",
        }
        and str in get_args(annotation)
        and custom_event.event_name == "custom_module_event"
    )


async def _test_event_info_roundtrip():
    target_id = "QQBot|Group|event_info_roundtrip"
    sender_id = "QQBot|event_info_roundtrip_user"
    target = await TargetUnionInfo.get_by_target_id(target_id)
    await target.edit_target_data("command_prefix", ["!", "！"])

    event = await EventInfo.assign(
        event_name="member_joined",
        target_id=target_id,
        target_from="QQBot|Group",
        client_name="QQBot",
        sender_id=sender_id,
        sender_from="QQBot",
        data={"event_id": "event-1"},
    )
    serialized = converter.unstructure(event)
    restored = converter.structure(serialized, EventInfo)
    await restored.refresh_info()

    return (
        isinstance(restored.target_union_info, TargetUnionInfo)
        and isinstance(restored.sender_union_info, SenderUnionInfo)
        and restored.target_union_id == event.target_union_id
        and restored.sender_union_id == event.sender_union_id
        and restored.prefixes[:2] == ["!", "！"]
        and restored.data == {"event_id": "event-1"}
        and "read_all_messages" not in serialized
    )


async def _test_event_dispatch():
    module_name = "__test_event_dispatch"
    target_id = "QQBot|Group|event_dispatch"
    received = []
    try:
        module = Module.assign(module_name=module_name, alias=None, recommend_modules=None, developers=None)
        module._db_load = True
        ModulesManager.add_module(module, "test.py")

        async def handler(event: EventInfo):
            received.append(event)
            return event.data["value"]

        Bind.Module(module_name).event("updated")(handler)
        ModulesManager.refresh()
        target = await TargetUnionInfo.get_by_target_id(target_id)
        await target.config_module(module_name, True)
        event = await EventInfo.assign(
            event_name="updated",
            target_id=target_id,
            target_from="QQBot|Group",
            client_name="QQBot",
            sender_id="QQBot|event_dispatch_user",
            sender_from="QQBot",
            data={"value": 1},
        )

        result = await ModulesManager.dispatch_event(event)
        module._db_load = False
        disabled_result = await ModulesManager.dispatch_event(event)
        return received == [event] and result == [1] and disabled_result == []
    finally:
        _remove_test_module(module_name)


async def _test_scoped_event_dispatch():
    module_name = "__test_scoped_event_dispatch"
    received = []
    try:
        module = Module.assign(
            module_name=module_name,
            alias=None,
            recommend_modules=None,
            developers=None,
            event=True,
            available_for="QQBot|Group",
        )
        module._db_load = True
        ModulesManager.add_module(module, "test.py")

        async def handler(event: EventInfo):
            received.append(event)

        Bind.Module(module_name).event("member_joined", available_for="QQBot|Group")(handler)
        ModulesManager.refresh()

        group_target_id = "QQBot|Group|event_scope"
        group_target = await TargetUnionInfo.get_by_target_id(group_target_id)
        group_event = await EventInfo.assign(
            event_name="member_joined",
            target_id=group_target_id,
            target_from="QQBot|Group",
            client_name="QQBot",
            sender_id="QQBot|event_scope_user",
            sender_from="QQBot",
        )
        await ModulesManager.dispatch_event(group_event)
        await group_target.config_module(module_name, True)
        await group_event.refresh_info()
        await ModulesManager.dispatch_event(group_event)

        guild_target_id = "QQBot|Guild|event_scope"
        guild_target = await TargetUnionInfo.get_by_target_id(guild_target_id)
        await guild_target.config_module(module_name, True)
        guild_event = await EventInfo.assign(
            event_name="member_joined",
            target_id=guild_target_id,
            target_from="QQBot|Guild",
            client_name="QQBot",
            sender_id="QQBot|Tiny|event_scope_user",
            sender_from="QQBot|Tiny",
        )
        await ModulesManager.dispatch_event(guild_event)

        return (
            received == [group_event]
            and received[0].target_union_id == group_target.union_id
            and received[0].sender_union_id is not None
        )
    finally:
        _remove_test_module(module_name)


async def _test_client_event_conversion():
    event = await EventInfo.assign(
        event_name="updated",
        target_id="QQBot|Group|event_client_conversion",
        target_from="QQBot|Group",
        client_name="QQBot",
        sender_id="QQBot|event_client_conversion_user",
        sender_from="QQBot",
        data={"value": 3},
    )
    captured = {}

    async def add_job(target_client, action, args, wait=True):
        captured.update(target_client=target_client, action=action, args=args, wait=wait)
        return "task-id"

    with patch.object(JobQueueClient, "add_job", new=add_job):
        result = await JobQueueClient.send_event_to_server(event)

    serialized = captured["args"]["event_info"]
    return (
        result == "task-id"
        and captured["target_client"] == "Server"
        and captured["action"] == "receive_event_from_client"
        and captured["wait"] is False
        and serialized["event_name"] == "updated"
        and serialized["data"] == {"value": 3}
        and serialized["target_union_info"]["union_id"] == event.target_union_id
        and serialized["sender_union_info"]["union_id"] == event.sender_union_id
        and "read_all_messages" not in serialized
    )


async def _test_bot_process_event():
    send_event = AsyncMock(return_value="task-id")
    event = await EventInfo.assign(
        event_name="updated",
        target_id="QQBot|Group|event_bot_process",
        target_from="QQBot|Group",
        client_name="QQBot",
    )
    with patch.object(JobQueueClient, "send_event_to_server", new=send_event):
        result = await Bot.process_event(event)

    send_event.assert_awaited_once_with(event)
    return result == "task-id"


async def _test_server_event_dispatch():
    event = await EventInfo.assign(
        event_name="updated",
        target_id="QQBot|Group|event_server_dispatch",
        target_from="QQBot|Group",
        client_name="QQBot",
        sender_id="QQBot|event_server_dispatch_user",
        sender_from="QQBot",
        data={"value": 5},
    )
    dispatch = AsyncMock(return_value=[])
    handler = JobQueueServer.queue_actions["receive_event_from_client"]
    with patch.object(ModulesManager, "dispatch_event", new=dispatch):
        result = await handler(
            SimpleNamespace(),
            {"event_info": converter.unstructure(event)},
        )

    dispatched = dispatch.await_args.args[0]
    return (
        result == {"success": True}
        and isinstance(dispatched, EventInfo)
        and isinstance(dispatched.target_union_info, TargetUnionInfo)
        and isinstance(dispatched.sender_union_info, SenderUnionInfo)
        and dispatched.event_name == "updated"
        and dispatched.data == {"value": 5}
    )


@func_case
async def test_event(tester: Tester):
    """模块事件：注册、EventInfo、队列转换与服务器分发测试。"""
    await tester.test(_test_event_binding, "模块事件绑定测试")
    await tester.test(_test_event_name_literal_hint, "EventInfo 事件名提示与自定义事件兼容测试")
    await tester.test(_test_event_info_roundtrip, "EventInfo 序列化与场景前缀测试")
    await tester.test(_test_event_dispatch, "模块事件分发与加载状态测试")
    await tester.test(_test_scoped_event_dispatch, "事件平台作用域与场景启用测试")
    await tester.test(_test_client_event_conversion, "客户端事件序列化测试")
    await tester.test(_test_bot_process_event, "Bot.process_event 转发测试")
    await tester.test(_test_server_event_dispatch, "服务器事件分发测试")
    return tester
