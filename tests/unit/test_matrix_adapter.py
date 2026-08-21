"""Matrix 消息适配器的边界行为单元测试。"""

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, call, patch

import bots.matrix.bot as matrix_bot_module
import bots.matrix.context as matrix_context
import nio
from bots.matrix.info import client_name, sender_prefix, target_prefix
from bots.matrix.features import features as matrix_features
from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import Image, Mention, Plain
from core.builtins.session.info import SessionInfo
from core.tester import Tester, func_case


async def _test_invalid_matrix_image_is_ignored():
    event = SimpleNamespace(source={"content": {"msgtype": "m.image", "body": "broken"}})
    mxc_to_http = AsyncMock(return_value="https://invalid")
    with patch.object(matrix_bot_module.matrix_bot, "mxc_to_http", new=mxc_to_http):
        chain = await matrix_bot_module.to_message_chain(event, target_id="Matrix|Room|1")
    return not chain.values and mxc_to_http.await_count == 0


async def _test_matrix_image_preserves_detected_mimetype():
    with TemporaryDirectory() as directory:
        image_path = Path(directory) / "sample.jpg"
        image_path.write_bytes(b"not-a-real-image")
        session = SessionInfo(
            target_id=f"{target_prefix}|!room:test",
            target_from=target_prefix,
            sender_id=f"{sender_prefix}|user:test",
            sender_from=sender_prefix,
            client_name=client_name,
            session_id="matrix-image-mimetype",
            support_image=True,
        )
        upload = AsyncMock(return_value=(SimpleNamespace(content_uri="mxc://test/image"), {}))
        room_send = AsyncMock(return_value=SimpleNamespace(event_id="$sent"))
        with (
            patch.object(matrix_context.matrix_bot, "upload", new=upload),
            patch.object(matrix_context.matrix_bot, "room_send", new=room_send),
            patch.object(matrix_context.matrix_bot, "encrypted_rooms", new=set()),
        ):
            result = await matrix_context.MatrixContextManager.send_message(
                session,
                MessageChain.assign(Image(image_path)),
                quote=False,
                enable_split_image=False,
            )
    return result == ["$sent"] and upload.await_args.kwargs["content_type"] == "image/jpeg"


async def _test_matrix_private_room_handles_error_response():
    class FakeErrorResponse:
        pass

    existing = SimpleNamespace(
        room_id="!existing:test",
        join_rule="invite",
        member_count=2,
        users={"@user:test"},
        invited_users=set(),
    )
    rooms = {existing.room_id: existing}
    session = SimpleNamespace(get_common_target_id=lambda: "@user:test")
    room_create = AsyncMock(return_value=SimpleNamespace(room_id="!created:test"))
    with (
        patch.object(matrix_context.nio, "ErrorResponse", new=FakeErrorResponse),
        patch.object(matrix_context.matrix_bot, "rooms", new=rooms),
        patch.object(
            matrix_context.matrix_bot, "room_get_state_event", new=AsyncMock(return_value=FakeErrorResponse())
        ),
        patch.object(matrix_context.matrix_bot, "room_create", new=room_create),
    ):
        try:
            room = await matrix_context.MatrixContextManager._resolve_matrix_room_(session)
        except Exception:
            return False
    return room.room_id == "!created:test" and "!created:test" not in rooms and room_create.await_count == 1


async def _test_matrix_private_room_create_error_returns_none():
    class FakeErrorResponse:
        pass

    session = SimpleNamespace(get_common_target_id=lambda: "@user:test")
    with (
        patch.object(matrix_context.nio, "ErrorResponse", new=FakeErrorResponse),
        patch.object(matrix_context.matrix_bot, "rooms", new={}),
        patch.object(matrix_context.matrix_bot, "room_create", new=AsyncMock(return_value=FakeErrorResponse())),
    ):
        room = await matrix_context.MatrixContextManager._resolve_matrix_room_(session)
    return room is None


async def _test_matrix_initial_sync_is_not_replayed():
    response = SimpleNamespace(next_batch="next")
    sync = AsyncMock(return_value=response)
    invited = AsyncMock()
    joined = AsyncMock()
    with (
        patch.object(matrix_bot_module.matrix_bot, "sync", new=sync),
        patch.object(matrix_bot_module.matrix_bot, "_handle_invited_rooms", new=invited),
        patch.object(matrix_bot_module.matrix_bot, "_handle_joined_rooms", new=joined),
    ):
        result = await matrix_bot_module._sync_room_state()
    return result is True and sync.await_count == 1 and invited.await_count == 0 and joined.await_count == 0


async def _test_matrix_reaction_filters_self_and_ignored_sender():
    room = SimpleNamespace(room_id="!room:test")
    assign = AsyncMock()
    process = AsyncMock()

    def reaction(sender):
        return SimpleNamespace(
            sender=sender,
            reacts_to="$message",
            event_id="$reaction",
            source={"content": {"m.relates_to": {"key": "✅"}}},
        )

    with (
        patch.object(matrix_bot_module.matrix_bot, "user_id", "@bot:test"),
        patch.object(matrix_bot_module, "ignored_sender", [f"{sender_prefix}|ignored:test"]),
        patch.object(matrix_bot_module.SessionInfo, "assign", new=assign),
        patch.object(matrix_bot_module.Bot, "process_message", new=process),
    ):
        await matrix_bot_module.on_reaction(room, reaction("@bot:test"))
        await matrix_bot_module.on_reaction(room, reaction("@ignored:test"))
    return assign.await_count == 0 and process.await_count == 0


async def _test_matrix_reaction_reply_quotes_origin_event():
    class FakeReactionEvent:
        sender = "@user:test"
        event_id = "$reaction"
        source = {"content": {"m.relates_to": {"rel_type": "m.annotation", "event_id": "$origin", "key": "✅"}}}

    room = SimpleNamespace(room_id="!room:test")
    event = FakeReactionEvent()
    session = SessionInfo(
        target_id=f"{target_prefix}|!room:test",
        target_from=target_prefix,
        sender_id=f"{sender_prefix}|user:test",
        sender_from=sender_prefix,
        client_name=client_name,
        session_id="matrix-reaction-reply",
        message_id="$reaction",
        reply_id="$origin",
    )
    room_send = AsyncMock(return_value=SimpleNamespace(event_id="$sent"))
    with (
        patch.object(matrix_context.nio, "ReactionEvent", new=FakeReactionEvent),
        patch.object(matrix_context.MatrixContextManager, "context", new={session.session_id: (room, event)}),
        patch.object(matrix_context.matrix_bot, "room_send", new=room_send),
    ):
        result = await matrix_context.MatrixContextManager.send_message(
            session,
            MessageChain.assign("hello"),
            quote=True,
        )
    content = room_send.await_args.args[2]
    return (
        result == ["$sent"]
        and content["m.relates_to"]["m.in_reply_to"]["event_id"] == "$origin"
        and session.message_id == "$reaction"
    )


async def _test_matrix_reaction_entry_preserves_event_and_origin_ids():
    room = SimpleNamespace(room_id="!room:test")
    event = SimpleNamespace(
        sender="@user:test",
        reacts_to="$origin",
        event_id="$reaction",
        source={"content": {"m.relates_to": {"event_id": "$origin", "key": "✅"}}},
    )
    assigned = SimpleNamespace()
    assign = AsyncMock(return_value=assigned)
    process = AsyncMock()
    with (
        patch.object(matrix_bot_module.matrix_bot, "user_id", "@bot:test"),
        patch.object(matrix_bot_module, "ignored_sender", []),
        patch.object(matrix_bot_module.SessionInfo, "assign", new=assign),
        patch.object(matrix_bot_module.Bot, "process_message", new=process),
    ):
        await matrix_bot_module.on_reaction(room, event)

    return (
        process.await_args.args == (assigned, (room, event))
        and assign.await_args.kwargs["message_id"] == "$reaction"
        and assign.await_args.kwargs["reply_id"] == "$origin"
        and assign.await_args.kwargs["messages"].to_str() == "✅"
    )


async def _test_matrix_reaction_operations_keep_event_and_origin_distinct():
    class FakeReactionEvent:
        sender = "@user:test"
        event_id = "$reaction"
        reacts_to = "$origin"
        source = {"content": {"m.relates_to": {"event_id": "$origin", "key": "✅"}}}

    room = SimpleNamespace(room_id="!room:test")
    event = FakeReactionEvent()
    session = SessionInfo(
        target_id=f"{target_prefix}|!room:test",
        target_from=target_prefix,
        sender_id=f"{sender_prefix}|user:test",
        sender_from=sender_prefix,
        client_name=client_name,
        session_id="matrix-reaction-operations",
        message_id="$reaction",
        reply_id="$origin",
    )
    room_send = AsyncMock(return_value=SimpleNamespace(event_id="$bot-added-reaction"))
    room_redact = AsyncMock(return_value=SimpleNamespace())
    relations = Mock()

    async def related_events():
        yield SimpleNamespace(
            sender="@other:test",
            event_id="$other-reaction",
            key="🔥",
            source={"content": {"m.relates_to": {"key": "🔥"}}},
        )
        yield SimpleNamespace(
            sender="@bot:test",
            event_id="$bot-reaction",
            key="🔥",
            source={"content": {"m.relates_to": {"key": "🔥"}}},
        )

    relations.return_value = related_events()
    with (
        patch.object(matrix_context.nio, "ReactionEvent", new=FakeReactionEvent),
        patch.object(matrix_context.MatrixContextManager, "context", new={session.session_id: (room, event)}),
        patch.object(matrix_context.matrix_bot, "user_id", "@bot:test"),
        patch.object(matrix_context.matrix_bot, "room_send", new=room_send),
        patch.object(matrix_context.matrix_bot, "room_redact", new=room_redact),
        patch.object(matrix_context.matrix_bot, "room_get_event_relations", new=relations),
    ):
        await matrix_context.MatrixContextManager.delete_message(session, session.message_id)
        await matrix_context.MatrixContextManager.add_reaction(session, session.message_id, "🔥")
        await matrix_context.MatrixContextManager.remove_reaction(session, session.message_id, "🔥")

    added_content = room_send.await_args.kwargs["content"]
    return (
        room_redact.await_args_list
        == [
            call("!room:test", "$reaction", None),
            call("!room:test", "$bot-reaction"),
        ]
        and added_content["m.relates_to"] == {"rel_type": "m.annotation", "event_id": "$origin", "key": "🔥"}
        and relations.call_args.args == ("!room:test", "$origin")
        and relations.call_args.kwargs
        == {"rel_type": matrix_context.RelationshipType.annotation, "event_type": "m.reaction"}
    )


def _test_matrix_does_not_advertise_unimplemented_restriction():
    return matrix_features.support_manage is False


async def _test_matrix_permission_state_error_returns_false():
    session = SimpleNamespace(
        session_id="matrix-permission-error",
        get_common_target_id=lambda: "!room:test",
        get_common_sender_id=lambda: "user:test",
    )
    with (
        patch.object(
            matrix_context.matrix_bot,
            "room_get_event",
            new=AsyncMock(return_value=nio.RoomGetEventError("unsupported")),
        ),
        patch.object(
            matrix_context.matrix_bot,
            "room_get_state_event",
            new=AsyncMock(return_value=nio.RoomGetStateEventError("unavailable")),
        ),
    ):
        try:
            result = await matrix_context.MatrixContextManager.check_native_permission(session)
        except Exception:
            return False
    return result is False


async def _test_matrix_upload_error_returns_empty_result():
    with TemporaryDirectory() as directory:
        image_path = Path(directory) / "sample.png"
        image_path.write_bytes(b"not-a-real-image")
        session = SessionInfo(
            target_id=f"{target_prefix}|!room:test",
            target_from=target_prefix,
            sender_id=f"{sender_prefix}|user:test",
            sender_from=sender_prefix,
            client_name=client_name,
            session_id="matrix-upload-error",
            support_image=True,
        )
        room_send = AsyncMock()
        with (
            patch.object(
                matrix_context.matrix_bot,
                "upload",
                new=AsyncMock(return_value=(nio.UploadError("upload failed"), {})),
            ),
            patch.object(matrix_context.matrix_bot, "room_send", new=room_send),
            patch.object(matrix_context.matrix_bot, "encrypted_rooms", new=set()),
        ):
            try:
                result = await matrix_context.MatrixContextManager.send_message(
                    session,
                    MessageChain.assign(Image(image_path)),
                    quote=False,
                    enable_split_image=False,
                )
            except Exception:
                return False
    return result == [] and room_send.await_count == 0


async def _test_matrix_send_exception_returns_empty_result():
    session = SessionInfo(
        target_id=f"{target_prefix}|!room:test",
        target_from=target_prefix,
        sender_id=f"{sender_prefix}|user:test",
        sender_from=sender_prefix,
        client_name=client_name,
        session_id="matrix-send-exception",
    )
    with patch.object(
        matrix_context.matrix_bot,
        "room_send",
        new=AsyncMock(side_effect=RuntimeError("send failed")),
    ):
        try:
            result = await matrix_context.MatrixContextManager.send_message(
                session,
                MessageChain.assign("hello"),
                quote=False,
            )
        except Exception:
            return False
    return result == []


async def _test_matrix_preserves_ids_before_send_failure():
    session = SessionInfo(
        target_id=f"{target_prefix}|!room:test",
        target_from=target_prefix,
        sender_id=f"{sender_prefix}|user:test",
        sender_from=sender_prefix,
        client_name=client_name,
        session_id="matrix-partial-send",
        support_mention=True,
    )
    room_send = AsyncMock(side_effect=[SimpleNamespace(event_id="$first"), RuntimeError("send failed")])
    with patch.object(matrix_context.matrix_bot, "room_send", new=room_send):
        result = await matrix_context.MatrixContextManager.send_message(
            session,
            MessageChain.assign([Plain("hello"), Mention("Matrix|other:test")]),
            quote=False,
        )
    return result == ["$first"] and room_send.await_count == 2


async def _test_matrix_management_error_responses_are_not_logged_as_success():
    session = SimpleNamespace(
        session_id="matrix-management-error",
        target_id=f"{target_prefix}|!room:test",
        get_common_target_id=lambda: "!room:test",
    )
    info = Mock()
    error = Mock()
    context = {session.session_id: (None, None)}
    with (
        patch.object(
            matrix_context.matrix_bot,
            "room_redact",
            new=AsyncMock(return_value=nio.RoomRedactError("redact failed")),
        ),
        patch.object(
            matrix_context.matrix_bot,
            "room_kick",
            new=AsyncMock(return_value=nio.RoomKickError("kick failed")),
        ),
        patch.object(
            matrix_context.matrix_bot,
            "room_ban",
            new=AsyncMock(return_value=nio.RoomBanError("ban failed")),
        ),
        patch.object(
            matrix_context.matrix_bot,
            "room_unban",
            new=AsyncMock(return_value=nio.RoomUnbanError("unban failed")),
        ),
        patch.object(
            matrix_context.matrix_bot,
            "room_send",
            new=AsyncMock(return_value=nio.RoomSendError("reaction failed")),
        ),
        patch.object(matrix_context.MatrixContextManager, "context", new=context),
        patch.object(matrix_context.Logger, "info", new=info),
        patch.object(matrix_context.Logger, "error", new=error),
    ):
        await matrix_context.MatrixContextManager.delete_message(session, "$message", "reason")
        await matrix_context.MatrixContextManager.kick_member(session, "Matrix|user:test", "reason")
        await matrix_context.MatrixContextManager.ban_member(session, "Matrix|user:test", "reason")
        await matrix_context.MatrixContextManager.unban_member(session, "Matrix|user:test")
        await matrix_context.MatrixContextManager.add_reaction(session, "$message", "✅")

    return info.call_count == 0 and error.call_count == 5


@func_case
async def test_matrix_adapter(tester: Tester):
    """Matrix 输入与媒体发送必须安全处理缺失字段和 MIME 类型。"""
    await tester.test(_test_invalid_matrix_image_is_ignored, "Matrix 无 URL 图片被忽略")
    await tester.test(_test_matrix_image_preserves_detected_mimetype, "Matrix 图片保留 MIME 类型")
    await tester.test(_test_matrix_private_room_handles_error_response, "Matrix 私聊房间处理错误响应")
    await tester.test(_test_matrix_private_room_create_error_returns_none, "Matrix 私聊房间创建错误返回空")
    await tester.test(_test_matrix_initial_sync_is_not_replayed, "Matrix 初始同步不重复回放")
    await tester.test(_test_matrix_reaction_filters_self_and_ignored_sender, "Matrix Reaction 过滤机器人和忽略用户")
    await tester.test(_test_matrix_reaction_reply_quotes_origin_event, "Matrix Reaction 回复引用原消息")
    await tester.test(
        _test_matrix_reaction_entry_preserves_event_and_origin_ids,
        "Matrix Reaction 入口保留事件与原消息 ID",
    )
    await tester.test(
        _test_matrix_reaction_operations_keep_event_and_origin_distinct,
        "Matrix Reaction 删除事件且操作原消息",
    )
    await tester.test(
        _test_matrix_does_not_advertise_unimplemented_restriction,
        "Matrix 不声明未实现的成员限制能力",
    )
    await tester.test(_test_matrix_permission_state_error_returns_false, "Matrix 权限状态错误安全返回")
    await tester.test(_test_matrix_upload_error_returns_empty_result, "Matrix 上传错误返回空消息 ID")
    await tester.test(_test_matrix_send_exception_returns_empty_result, "Matrix 发送异常返回空消息 ID")
    await tester.test(_test_matrix_preserves_ids_before_send_failure, "Matrix 后续失败保留已发送 ID")
    await tester.test(
        _test_matrix_management_error_responses_are_not_logged_as_success,
        "Matrix 管理错误响应不得记录成功",
    )
    return tester
