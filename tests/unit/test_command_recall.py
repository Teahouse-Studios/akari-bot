"""撤回触发消息后的命令收尾测试。"""

import asyncio
from unittest.mock import AsyncMock, patch

from core.builtins.session.command_lifecycle import CommandLifecycleRegistry
from core.builtins.session.info import EventInfo, SessionInfo
from core.builtins.session.internal import MessageSession
from core.builtins.session.lock import ExecutionLockList
from core.i18n import Locale
from core.queue.contracts import PlatformAPI
from core.tester import Tester, func_case
from core.tester.timing import TIME_SCALE


def _msg(message_id: str, delete: bool = True, private: bool = False) -> MessageSession:
    return MessageSession(
        session_info=SessionInfo(
            target_id="TEST|Group|1",
            target_from="TEST|Group",
            client_name="TEST",
            sender_id="TEST|1",
            sender_from="TEST",
            message_id=message_id,
            session_id=f"session-{message_id}",
            locale=Locale("zh_cn"),
            support_delete=delete,
            support_private_msg=private,
        )
    )


def _recall(
    message_id: str,
    operator_id: str | None = "TEST|1",
    target_id: str = "TEST|Group|1",
) -> EventInfo:
    return EventInfo(
        event_name="message_recalled",
        data={"message_id": message_id, "operator_id": operator_id},
        target_id=target_id,
        client_name="TEST",
    )


def _reset() -> None:
    CommandLifecycleRegistry.clear()
    ExecutionLockList._list.clear()
    ExecutionLockList._reservations.clear()


async def _test_finished_command_outputs_deleted_later() -> bool:
    _reset()
    msg = _msg("cmd-done")

    async def _command():
        CommandLifecycleRegistry.attach(msg)
        CommandLifecycleRegistry.record_output(msg, ["out-1", "out-2"])
        CommandLifecycleRegistry.finish(msg)

    task = asyncio.create_task(_command())
    delete = AsyncMock()
    try:
        await asyncio.wait({task}, timeout=5 * TIME_SCALE)
        with patch.object(PlatformAPI.delete_message, "submit", new=delete):
            handled = await CommandLifecycleRegistry.handle_message_recall(_recall("cmd-done"))
        return handled and delete.await_count == 1 and delete.await_args.args[1] == ["out-1", "out-2"]
    finally:
        _reset()


async def _test_running_command_is_cancelled_and_sends_blocked() -> bool:
    _reset()
    msg = _msg("cmd-cancel")
    started = asyncio.Event()
    cleaned = asyncio.Event()
    observed = {}

    async def _long_command():
        CommandLifecycleRegistry.attach(msg)
        CommandLifecycleRegistry.record_output(msg, ["out-1"])
        started.set()
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            send = AsyncMock(return_value=["late-out"])
            with patch.object(PlatformAPI, "send_message", new=send):
                sent = await msg.send_message("late", quote=False)
            observed["send_calls"] = send.await_count
            observed["sent_ids"] = sent.message_id if sent is not None else None
            raise
        finally:
            cleaned.set()
            CommandLifecycleRegistry.finish(msg)

    task = asyncio.create_task(_long_command())
    delete = AsyncMock()
    try:
        await asyncio.wait_for(started.wait(), timeout=5 * TIME_SCALE)
        with patch.object(PlatformAPI.delete_message, "submit", new=delete):
            handled = await CommandLifecycleRegistry.handle_message_recall(_recall("cmd-cancel"))
        await asyncio.wait({task}, timeout=5 * TIME_SCALE)
        return (
            handled
            and task.cancelled()
            and cleaned.is_set()
            and observed.get("send_calls") == 0
            and observed.get("sent_ids") == []
            and delete.await_args.args[1] == ["out-1"]
        )
    finally:
        if not task.done():
            task.cancel()
            await asyncio.wait({task}, timeout=5 * TIME_SCALE)
        _reset()


async def _test_unrelated_recall_is_ignored() -> bool:
    _reset()
    msg = _msg("cmd-a")

    async def _command():
        CommandLifecycleRegistry.attach(msg)
        CommandLifecycleRegistry.record_output(msg, ["out-a"])
        CommandLifecycleRegistry.finish(msg)

    task = asyncio.create_task(_command())
    delete = AsyncMock()
    try:
        await asyncio.wait({task}, timeout=5 * TIME_SCALE)
        with patch.object(PlatformAPI.delete_message, "submit", new=delete):
            other_message = await CommandLifecycleRegistry.handle_message_recall(_recall("cmd-b"))
            other_target = await CommandLifecycleRegistry.handle_message_recall(
                _recall("cmd-a", target_id="TEST|Group|2")
            )
        return not other_message and not other_target and delete.await_count == 0
    finally:
        _reset()


async def _test_recall_without_delete_support_only_cancels() -> bool:
    _reset()
    msg = _msg("cmd-nodelete", delete=False)
    started = asyncio.Event()

    async def _long_command():
        CommandLifecycleRegistry.attach(msg)
        CommandLifecycleRegistry.record_output(msg, ["out-1"])
        started.set()
        try:
            await asyncio.sleep(30)
        finally:
            CommandLifecycleRegistry.finish(msg)

    task = asyncio.create_task(_long_command())
    delete = AsyncMock()
    try:
        await asyncio.wait_for(started.wait(), timeout=5 * TIME_SCALE)
        with patch.object(PlatformAPI.delete_message, "submit", new=delete):
            handled = await CommandLifecycleRegistry.handle_message_recall(_recall("cmd-nodelete"))
        await asyncio.wait({task}, timeout=5 * TIME_SCALE)
        return handled and task.cancelled() and delete.await_count == 0
    finally:
        if not task.done():
            task.cancel()
            await asyncio.wait({task}, timeout=5 * TIME_SCALE)
        _reset()


async def _test_recall_by_other_operator_is_ignored() -> bool:
    _reset()
    msg = _msg("cmd-admin")
    started = asyncio.Event()

    async def _long_command():
        CommandLifecycleRegistry.attach(msg)
        CommandLifecycleRegistry.record_output(msg, ["out-1"])
        started.set()
        try:
            await asyncio.sleep(30)
        finally:
            CommandLifecycleRegistry.finish(msg)

    task = asyncio.create_task(_long_command())
    delete = AsyncMock()
    try:
        await asyncio.wait_for(started.wait(), timeout=5 * TIME_SCALE)
        with patch.object(PlatformAPI.delete_message, "submit", new=delete):
            handled = await CommandLifecycleRegistry.handle_message_recall(_recall("cmd-admin", operator_id="TEST|2"))
        return not handled and delete.await_count == 0 and not task.done()
    finally:
        if not task.done():
            task.cancel()
            await asyncio.wait({task}, timeout=5 * TIME_SCALE)
        _reset()


async def _test_private_outputs_are_not_recorded() -> bool:
    _reset()
    msg = _msg("cmd-private", private=True)

    async def _command():
        CommandLifecycleRegistry.attach(msg)
        await msg.send_private_message("hi", user_id="TEST|1")
        CommandLifecycleRegistry.finish(msg)

    task = asyncio.create_task(_command())
    delete = AsyncMock()
    try:
        with patch.object(PlatformAPI, "send_private_msg", new=AsyncMock(return_value=["dm-1"])):
            await asyncio.wait({task}, timeout=5 * TIME_SCALE)
        with patch.object(PlatformAPI.delete_message, "submit", new=delete):
            handled = await CommandLifecycleRegistry.handle_message_recall(_recall("cmd-private"))
        return not handled and delete.await_count == 0
    finally:
        _reset()


@func_case
async def test_command_recall(tester: Tester):
    """撤回触发消息后终止命令并删除已发送的输出。"""
    await tester.test(_test_finished_command_outputs_deleted_later, "命令结束后撤回仍删除全部输出")
    await tester.test(_test_running_command_is_cancelled_and_sends_blocked, "执行中撤回终止命令并拦截后续发送")
    await tester.test(_test_unrelated_recall_is_ignored, "无关场景或消息的撤回被忽略")
    await tester.test(_test_recall_without_delete_support_only_cancels, "不支持删除时只终止命令")
    await tester.test(_test_recall_by_other_operator_is_ignored, "他人撤回命令消息不触发收尾")
    await tester.test(_test_private_outputs_are_not_recorded, "私信输出不计入场景撤回清理")
    return tester
