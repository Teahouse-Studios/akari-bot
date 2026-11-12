"""modules.core.common_tools.bind 单元测试 - 消息通道的主动推送优先级（需要数据库）。"""

from unittest.mock import patch

import modules.core.common_tools.bind as bind
from core.builtins.message.elements import I18NContextElement
from core.builtins.session.info import SessionInfo
from core.builtins.session.internal import MessageSession
from core.constants.exceptions import SessionFinished
from core.database.models import TargetUnionBind, TargetUnionInfo
from core.tester import func_case, Tester

ENTRY_KEY = "core.message.bind.channel.info.entry"


async def _session(prefix: str) -> MessageSession:
    session_info = await SessionInfo.assign(
        target_id=f"{prefix}|X|1",
        target_from=f"{prefix}|X",
        client_name=prefix,
        sender_id=f"{prefix}|1",
        create=True,
    )
    return MessageSession(session_info=session_info)


async def _call(handler, prefix: str, *args) -> list:
    msg = await _session(prefix)
    sent = []

    async def _finish(self, message_chain=None, **_):
        sent.extend(message_chain if isinstance(message_chain, list) else [message_chain])
        raise SessionFinished

    with patch.object(MessageSession, "finish", _finish):
        try:
            await handler(msg, *args)
        except SessionFinished:
            pass
    return sent


def _entries(lines: list) -> list[I18NContextElement]:
    return [line for line in lines if isinstance(line, I18NContextElement) and line.key == ENTRY_KEY]


async def _test_set_priority_persists():
    try:
        sent = await _call(bind._set_channel_priority, "PRIOA", 7)
        row = await TargetUnionBind.get(target_id="PRIOA|X|1")
        element = sent[-1]
        return (
            row.push_priority == 7
            and element.key == "core.message.bind.channel.priority.set.success"
            and element.kwargs == {"priority": 7}
        )

    except Exception:
        return False


async def _test_invalid_priority_is_rejected():
    try:
        for priority in (101, -1):
            sent = await _call(bind._set_channel_priority, "PRIOB", priority)
            row = await TargetUnionBind.get(target_id="PRIOB|X|1")
            if row.push_priority != 0 or sent[-1].key != "core.message.bind.channel.priority.invalid":
                return False
        return True

    except Exception:
        return False


async def _test_reset_priority():
    try:
        await _call(bind._set_channel_priority, "PRIOC", 9)
        sent = await _call(bind._reset_channel_priority, "PRIOC")
        row = await TargetUnionBind.get(target_id="PRIOC|X|1")
        return row.push_priority == 0 and sent[-1].key == "core.message.bind.channel.priority.reset.success"

    except Exception:
        return False


async def _test_channel_view_lists_push_order():
    try:
        union = await TargetUnionInfo.resolve_union("PRIOD|X|1")
        await union.bind_id("PRIOD|X|2")
        await TargetUnionBind.filter(union_id=union.union_id).update(channel_id=1)
        await TargetUnionBind.set_push_priority("PRIOD|X|2", 10)

        msg = await _session("PRIOD")
        entries = _entries(await bind._channel_lines(msg))
        return (
            [entry.kwargs["id"] for entry in entries] == ["PRIOD|X|2", "PRIOD|X|1"]
            and [entry.kwargs["priority"] for entry in entries] == [10, 0]
            and all(entry.disable_joke for entry in entries)
        )

    except Exception:
        return False


@func_case
async def test_bind_channel(tester: Tester):
    """modules.core.common_tools.bind: 消息通道推送优先级命令测试"""
    await tester.test(_test_set_priority_persists, "推送优先级设置持久化测试")
    await tester.test(_test_invalid_priority_is_rejected, "推送优先级越界拒绝测试")
    await tester.test(_test_reset_priority, "推送优先级重置测试")
    await tester.test(_test_channel_view_lists_push_order, "消息通道按推送顺序展示测试")

    return tester
