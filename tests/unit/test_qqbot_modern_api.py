"""QQBot 适配器对 botpy 翻新接口的接入测试。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from botpy.errors import ServerError
from botpy.message import GroupMessage
from botpy.protocol import MediaSendResult

import bots.qqbot.context as qqbot_context
from bots.qqbot.config import QQBotConfig
from bots.qqbot.context import QQBotContextManager, _message_ids, _reply_target, _resolve_api_message_id
from bots.qqbot.info import (
    target_c2c_prefix,
    target_direct_prefix,
    target_group_prefix,
    target_guild_prefix,
)
from core.builtins.message.chain import MessageChain
from core.builtins.message.elements import (
    AudioElement,
    ImageElement,
    MarkdownElement,
    MentionElement,
    PlainElement,
    VideoElement,
)
from core.builtins.session.info import SessionInfo
from core.logger import Logger
from core.tester import func_case, Tester

with patch.object(QQBotConfig, "enable", False):
    import bots.qqbot.bot as qqbot_bot


def _make_session(target_from: str, target: str = "target") -> SessionInfo:
    return SessionInfo(
        target_id=f"{target_from}|{target}",
        sender_id="QQBot|sender",
        target_from=target_from,
        client_name="QQBot",
        session_id=f"modern-{target_from}",
        message_id="source-message",
    )


def _test_reply_target_scopes() -> bool:
    expected = {
        target_c2c_prefix: "c2c",
        target_group_prefix: "group",
        target_guild_prefix: "channel",
        target_direct_prefix: "dm",
    }
    for target_from, scope in expected.items():
        session = _make_session(target_from)
        passive = _reply_target(session, object())
        proactive = _reply_target(session)
        if passive.scope != scope or passive.target_id != "target" or passive.message_id != "source-message":
            Logger.error(f"Unexpected passive target for {target_from}: {passive}")
            return False
        if proactive.scope != scope or proactive.message_id is not None:
            Logger.error(f"Unexpected proactive target for {target_from}: {proactive}")
            return False
    return True


def _test_message_id_collection() -> bool:
    result = [
        {"id": "ROBOT-plain", "ext_info": {"ref_idx": "REFIDX-plain"}},
        MediaSendResult(
            upload={"file_info": "image"},
            message={"id": "ROBOT-image", "ext_info": {"msg_idx": "REFIDX-image"}},
        ),
        {"id": "legacy-id"},
        {"id": "ROBOT-without-index"},
        None,
    ]
    return (
        _message_ids(result) == ["REFIDX-plain", "REFIDX-image", "legacy-id"]
        and _resolve_api_message_id("REFIDX-plain") == "ROBOT-plain"
        and _resolve_api_message_id("REFIDX-image") == "ROBOT-image"
    )


class _FakeClient:
    def __init__(self):
        self.recalls = []

    async def recall_message(self, target, message_id, *, hidetip=False):
        self.recalls.append((target, message_id, hidetip))


class _FailingSendClient:
    def __init__(self, code: int, fallback_code: int | None = None):
        self.code = code
        self.fallback_code = fallback_code
        self.calls = []
        self.uploads = []

    def _record(self, target, kwargs):
        self.calls.append((target.scope, target.target_id, target.message_id, dict(kwargs)))
        code = self.code if len(self.calls) == 1 else self.fallback_code
        if code is not None:
            messages = {
                40034005: "回复消息msg_id已过期",
                40034102: "主动消息失败, 无权限",
                40034105: "主动消息失败, 无权限",
                40034101: "机器人非群成员",
                40054002: "机器人已被禁言",
                40054003: "机器人不是群成员",
            }
            message = messages.get(code, "回复消息失败，被动回复时间或者次数超过限制")
            raise ServerError(
                message,
                status=400,
                code=code,
                response={"message": message, "code": code, "err_code": code},
            )

    async def send(self, target, **kwargs):
        self._record(target, kwargs)
        return {"id": "fallback"}

    async def send_markdown(self, target, content, keyboard=None):
        self._record(target, {"content": content, "keyboard": keyboard})
        return {"id": "fallback"}

    async def upload_media(self, target, file_type, **kwargs):
        self.uploads.append((target.scope, target.target_id, file_type, kwargs))
        return {"file_info": "uploaded-image"}


class _CaptureSendClient:
    def __init__(self):
        self.calls = []

    async def send(self, target, **kwargs):
        self.calls.append(("plain", kwargs))
        return {"id": "plain"}

    async def send_markdown(self, target, content, keyboard=None):
        self.calls.append(("markdown", {"content": content, "keyboard": keyboard}))
        return {"id": "markdown"}

    async def upload_media(self, target, file_type, **kwargs):
        self.calls.append(("upload", {"file_type": file_type, **kwargs}))
        return {"file_info": "uploaded-image"}


class _PartialFailClient(_CaptureSendClient):
    async def send(self, target, **kwargs):
        self.calls.append(("plain", kwargs))
        if len([call for call in self.calls if call[0] == "plain"]) == 1:
            return {"id": "first"}
        raise RuntimeError("second image failed")


class _PrivateCaptureClient(_CaptureSendClient):
    def __init__(self):
        super().__init__()
        self.api = SimpleNamespace(create_dms=AsyncMock(return_value={"guild_id": "dm-other"}))

    async def send(self, target, **kwargs):
        self.calls.append((target.scope, target.target_id, kwargs))
        return {"id": "private"}


async def _send_with_client(
    session: SessionInfo,
    client: _FailingSendClient | _CaptureSendClient,
    message: MessageChain | None = None,
) -> list[str]:
    previous_client = QQBotContextManager.client
    QQBotContextManager.client = client
    try:
        return await QQBotContextManager.send_message(session, message or MessageChain.assign("hello"))
    finally:
        QQBotContextManager.client = previous_client


async def _test_expired_reply_falls_back_to_proactive() -> bool:
    session = _make_session(target_group_prefix)
    client = _FailingSendClient(40034005)
    QQBotContextManager.context[session.session_id] = object()
    try:
        result = await _send_with_client(session, client)
    finally:
        QQBotContextManager.context.pop(session.session_id, None)

    if result != ["fallback"] or len(client.calls) != 2:
        Logger.error(f"Expected one proactive fallback, got result={result}, calls={client.calls}")
        return False
    first, second = client.calls
    if first[:3] != ("group", "target", "source-message") or second[:3] != ("group", "target", None):
        Logger.error(f"Reply target should lose only its message ID on fallback: {client.calls}")
        return False
    if first[3] != second[3]:
        Logger.error(f"Proactive fallback should preserve the message payload: {client.calls}")
        return False
    return True


async def _test_passive_reply_limit_falls_back_to_proactive() -> bool:
    session = _make_session(target_group_prefix)
    client = _FailingSendClient(40034128)
    QQBotContextManager.context[session.session_id] = object()
    try:
        result = await _send_with_client(session, client)
    finally:
        QQBotContextManager.context.pop(session.session_id, None)
    return result == ["fallback"] and [call[2] for call in client.calls] == ["source-message", None]


async def _test_fallback_without_proactive_permission_is_silent() -> bool:
    session = _make_session(target_group_prefix)
    client = _FailingSendClient(40034128, fallback_code=40034102)
    QQBotContextManager.context[session.session_id] = object()
    try:
        try:
            result = await _send_with_client(session, client)
        except ServerError:
            return False
    finally:
        QQBotContextManager.context.pop(session.session_id, None)
    return result == [] and [call[2] for call in client.calls] == ["source-message", None]


async def _test_proactive_permission_denied_is_silent() -> bool:
    for code in (40034102, 40034105):
        session = _make_session(target_group_prefix)
        client = _FailingSendClient(code)
        try:
            try:
                result = await _send_with_client(session, client)
            except ServerError:
                return False
        finally:
            QQBotContextManager.context.pop(session.session_id, None)
        if result != [] or len(client.calls) != 1 or client.calls[0][2] is not None:
            return False
    return True


async def _test_platform_proactive_permission_result_overrides_local_reply_target() -> bool:
    session = _make_session(target_group_prefix)
    client = _FailingSendClient(40034105)
    QQBotContextManager.context[session.session_id] = object()
    try:
        try:
            result = await _send_with_client(session, client)
        except ServerError:
            return False
    finally:
        QQBotContextManager.context.pop(session.session_id, None)
    return result == [] and len(client.calls) == 1 and client.calls[0][2] == "source-message"


async def _test_proactive_permission_message_is_silent_for_unknown_code() -> bool:
    session = _make_session(target_group_prefix)
    client = _FailingSendClient(49999999)
    client.code = 49999999
    original_record = client._record

    def record_with_permission_message(target, kwargs):
        client.calls.append((target.scope, target.target_id, target.message_id, dict(kwargs)))
        raise ServerError(
            "主动消息失败，无权限",
            status=400,
            code=client.code,
            response={"message": "主动消息失败，无权限", "code": client.code},
        )

    client._record = record_with_permission_message
    try:
        try:
            result = await _send_with_client(session, client)
        except ServerError:
            return False
    finally:
        client._record = original_record
    return result == [] and len(client.calls) == 1


async def _test_terminal_send_error_silently_aborts_without_proactive_fallback() -> bool:
    for code in (40034101, 40054002, 40054003):
        for has_context in (False, True):
            session = _make_session(target_group_prefix)
            client = _FailingSendClient(code)
            if has_context:
                QQBotContextManager.context[session.session_id] = object()
            try:
                try:
                    result = await _send_with_client(session, client)
                except ServerError:
                    return False
            finally:
                QQBotContextManager.context.pop(session.session_id, None)
            if result != [] or len(client.calls) != 1:
                return False
            expected_message_id = "source-message" if has_context else None
            if client.calls[0][2] != expected_message_id:
                return False
    return True


async def _test_terminal_send_error_stops_remaining_message_parts() -> bool:
    for code in (40034101, 40054002, 40054003):
        session = _make_session(target_group_prefix)
        client = _FailingSendClient(code)
        message = MessageChain.assign([ImageElement.assign(__file__), ImageElement.assign(__file__)])
        QQBotContextManager.context[session.session_id] = object()
        try:
            result = await _send_with_client(session, client, message)
        finally:
            QQBotContextManager.context.pop(session.session_id, None)
        if result != [] or len(client.calls) != 1 or len(client.uploads) != 2:
            return False
    return True


async def _test_audio_reply_limit_falls_back_to_proactive() -> bool:
    session = _make_session(target_group_prefix)
    client = _FailingSendClient(40034128)
    QQBotContextManager.context[session.session_id] = object()
    try:
        result = await _send_with_client(session, client, MessageChain.assign(AudioElement.assign(__file__)))
    finally:
        QQBotContextManager.context.pop(session.session_id, None)
    return (
        result == ["fallback"]
        and [call[2] for call in client.calls] == ["source-message", None]
        and len(client.uploads) == 1
    )


async def _test_markdown_reply_falls_back_to_proactive() -> bool:
    session = _make_session(target_group_prefix)
    session.support_markdown = True
    client = _FailingSendClient(40034005)
    QQBotContextManager.context[session.session_id] = object()
    try:
        with patch.object(qqbot_context, "qq_use_markdown", True):
            result = await _send_with_client(
                session,
                client,
                MessageChain.assign(MarkdownElement.assign("**hello**")),
            )
    finally:
        QQBotContextManager.context.pop(session.session_id, None)
    return result == ["fallback"] and [call[2] for call in client.calls] == ["source-message", None]


async def _test_image_reply_falls_back_to_proactive() -> bool:
    session = _make_session(target_group_prefix)
    client = _FailingSendClient(40034005)
    message = MessageChain.assign(ImageElement.assign(__file__))
    QQBotContextManager.context[session.session_id] = object()
    try:
        result = await _send_with_client(session, client, message)
    finally:
        QQBotContextManager.context.pop(session.session_id, None)
    return (
        result == ["fallback"]
        and [call[2] for call in client.calls] == ["source-message", None]
        and len(client.uploads) == 1
    )


async def _test_plain_image_is_uploaded_before_send() -> bool:
    """群聊 plain 图片须先 upload_media，发送阶段只提交 file_info 引用。"""
    session = _make_session(target_group_prefix)
    client = _CaptureSendClient()
    message = MessageChain.assign([PlainElement.assign("hello"), ImageElement.assign(__file__)])
    result = await _send_with_client(session, client, message)
    expected = [
        ("upload", {"file_type": 1, "local_path": __file__}),
        (
            "plain",
            {
                "content": "hello",
                "msg_type": 7,
                "media": {"file_info": "uploaded-image"},
            },
        ),
    ]
    if result != ["plain"] or client.calls != expected:
        Logger.error(f"Unexpected plain image preparation/send sequence: result={result}, calls={client.calls}")
        return False
    return True


async def _test_audio_video_are_sent_after_the_main_message() -> bool:
    session = _make_session(target_group_prefix)
    client = _CaptureSendClient()
    message = MessageChain.assign(
        [PlainElement.assign("hello"), AudioElement.assign(__file__), VideoElement.assign(__file__)]
    )
    with patch.object(qqbot_context, "qq_use_markdown", False):
        result = await _send_with_client(session, client, message)
    uploads = [call for call in client.calls if call[0] == "upload"]
    sends = [call for call in client.calls if call[0] == "plain"]
    return (
        result == ["plain", "plain", "plain"]
        and [call[1]["file_type"] for call in uploads]
        == [qqbot_context.MediaFileType.VOICE, qqbot_context.MediaFileType.VIDEO]
        and [call[1] for call in sends]
        == [
            {"content": "hello", "message_reference": None},
            {"msg_type": 7, "media": {"file_info": "uploaded-image"}},
            {"msg_type": 7, "media": {"file_info": "uploaded-image"}},
        ]
    )


async def _test_other_api_error_is_not_retried() -> bool:
    session = _make_session(target_group_prefix)
    client = _FailingSendClient(40034006)
    QQBotContextManager.context[session.session_id] = object()
    try:
        try:
            await _send_with_client(session, client)
        except ServerError as error:
            return error.code == 40034006 and len(client.calls) == 1
        return False
    finally:
        QQBotContextManager.context.pop(session.session_id, None)


async def _test_proactive_error_is_not_retried() -> bool:
    session = _make_session(target_group_prefix)
    client = _FailingSendClient(40034005)
    try:
        try:
            await _send_with_client(session, client)
        except ServerError as error:
            return error.code == 40034005 and len(client.calls) == 1
        return False
    finally:
        QQBotContextManager.context.pop(session.session_id, None)


async def _test_group_mention_plain_message() -> bool:
    session = _make_session(target_group_prefix)
    client = _CaptureSendClient()
    message = MessageChain.assign([MentionElement.assign("QQBot|member"), PlainElement.assign("hello")])
    with patch.object(qqbot_context, "qq_use_markdown", False):
        result = await _send_with_client(session, client, message)
    return result == ["plain"] and client.calls == [
        ("plain", {"content": "<@member>\nhello", "message_reference": None})
    ]


async def _test_group_mention_markdown_message() -> bool:
    session = _make_session(target_group_prefix)
    session.support_markdown = True
    client = _CaptureSendClient()
    message = MessageChain.assign([MentionElement.assign("QQBot|member"), PlainElement.assign("hello")])
    with patch.object(qqbot_context, "qq_use_markdown", True):
        result = await _send_with_client(session, client, message)
    return result == ["markdown"] and client.calls == [
        ("markdown", {"content": '<qqbot-at-user id="member" />\nhello', "keyboard": None})
    ]


async def _test_markdown_removes_line_break_before_at() -> bool:
    """Markdown payload 不应保留首个 at 标签前的换行。"""
    session = _make_session(target_group_prefix)
    session.support_markdown = True
    client = _CaptureSendClient()
    message = MessageChain.assign(MarkdownElement.assign('\r\n<qqbot-at-user id="member" />\nhello'))
    with patch.object(qqbot_context, "qq_use_markdown", True):
        result = await _send_with_client(session, client, message)
    return result == ["markdown"] and client.calls == [
        ("markdown", {"content": '<qqbot-at-user id="member" />\nhello', "keyboard": None})
    ]


async def _test_plain_allow_parse_controls_qq_atcode() -> bool:
    session = _make_session(target_group_prefix)
    client = _CaptureSendClient()
    message = MessageChain.assign(
        [
            PlainElement.assign("<AT:QQBot|raw>", allow_parse=False),
            PlainElement.assign("<AT:QQBot|parsed>"),
        ]
    )
    with patch.object(qqbot_context, "qq_use_markdown", False):
        result = await _send_with_client(session, client, message)
    return result == ["plain"] and client.calls == [
        ("plain", {"content": "<AT:QQBot|raw>\n<@parsed>", "message_reference": None})
    ]


async def _test_s3_failure_keeps_markdown_message_sendable() -> bool:
    class _FailingStorage:
        async def upload_temp(self, file_path):
            raise TimeoutError("S3 unavailable")

    session = _make_session(target_group_prefix)
    session.support_markdown = True
    client = _CaptureSendClient()
    message = MessageChain.assign([PlainElement.assign("hello"), ImageElement.assign(__file__)])
    with (
        patch.object(qqbot_context, "qq_use_markdown", True),
        patch.object(qqbot_context, "_load_s3_storage", return_value=_FailingStorage()),
    ):
        result = await _send_with_client(session, client, message)
    return result == ["markdown"] and client.calls == [("markdown", {"content": "hello", "keyboard": None})]


async def _test_plain_message_preserves_ids_before_later_send_failure() -> bool:
    session = _make_session(target_group_prefix)
    client = _PartialFailClient()
    message = MessageChain.assign([ImageElement.assign(__file__), ImageElement.assign(__file__)])
    result = await _send_with_client(session, client, message)
    sends = [call for call in client.calls if call[0] == "plain"]
    return result == ["first"] and len(sends) == 2


async def _test_private_message_uses_explicit_channel_user() -> bool:
    session = _make_session(target_guild_prefix, "guild|channel")
    session.sender_id = "QQBot|Tiny|current-user"
    client = _PrivateCaptureClient()
    previous_client = QQBotContextManager.client
    QQBotContextManager.client = client
    try:
        result = await QQBotContextManager.send_private_msg(
            session,
            "QQBot|Tiny|other-user",
            MessageChain.assign("secret"),
        )
    finally:
        QQBotContextManager.client = previous_client
    return (
        result == ["private"]
        and client.api.create_dms.await_count == 1
        and client.api.create_dms.await_args.kwargs == {"guild_id": "guild", "user_id": "other-user"}
        and client.calls == [("dm", "dm-other", {"content": "secret", "message_reference": None})]
    )


async def _test_private_message_does_not_reuse_another_users_dm() -> bool:
    session = _make_session(target_direct_prefix, "current-dm")
    session.sender_id = "QQBot|Tiny|current-user"
    client = _PrivateCaptureClient()
    previous_client = QQBotContextManager.client
    QQBotContextManager.client = client
    try:
        result = await QQBotContextManager.send_private_msg(
            session,
            "QQBot|Tiny|other-user",
            MessageChain.assign("secret"),
        )
    finally:
        QQBotContextManager.client = previous_client
    return result == [] and client.api.create_dms.await_count == 0 and client.calls == []


async def _test_private_message_client_failure_returns_empty() -> bool:
    session = _make_session(target_group_prefix)
    with patch("bots.qqbot.context._get_client", side_effect=RuntimeError("client unavailable")):
        try:
            result = await QQBotContextManager.send_private_msg(
                session,
                "QQBot|Client|other-user",
                MessageChain.assign("secret"),
            )
        except Exception:
            return False
    return result == []


async def _test_group_message_reply_uses_message_reference() -> bool:
    """普通群消息的 reply_id 应使用 message_scene 中的应用层引用 ID。"""
    message = SimpleNamespace(
        group_openid="group",
        author=SimpleNamespace(member_openid="sender", username="sender-name", member_role="member"),
        message_reference=SimpleNamespace(message_id="ROBOT-referenced"),
        message_scene={
            "ext": [
                "auth_token=token",
                "ref_msg_idx=REFIDX-referenced",
                "msg_idx=REFIDX-incoming",
            ]
        },
        mentions=[SimpleNamespace(id="mentioned-user")],
        content="hello",
        id="ROBOT-incoming",
    )
    session = SimpleNamespace()
    assign = AsyncMock(return_value=session)
    process_message = AsyncMock()
    with (
        patch.object(qqbot_bot.SessionInfo, "assign", new=assign),
        patch.object(qqbot_bot.Bot, "process_message", new=process_message),
        patch.object(qqbot_bot, "cache_permission"),
        patch.object(qqbot_bot, "resolve_features", return_value=SimpleNamespace()),
    ):
        await qqbot_bot.MyClient.on_message_group_create(message)

    return (
        assign.await_count == 1
        and assign.await_args.kwargs["message_id"] == "ROBOT-incoming"
        and assign.await_args.kwargs["reply_id"] == "REFIDX-referenced"
        and _resolve_api_message_id("REFIDX-incoming") == "ROBOT-incoming"
        and process_message.await_count == 1
    )


async def _test_group_quote_uses_api_message_id() -> bool:
    """平台引用参数必须使用 ROBOT ID，不能把 msg_idx 传给 OpenAPI。"""
    session = _make_session(target_group_prefix)
    session.message_id = "ROBOT-source"
    context = GroupMessage(
        None,
        "event",
        {
            "id": "ROBOT-source",
            "content": "source",
            "group_openid": "target",
            "author": {"member_openid": "sender", "username": "sender"},
            "message_scene": {"ext": ["msg_idx=REFIDX-source"]},
        },
    )
    client = _CaptureSendClient()
    QQBotContextManager.context[session.session_id] = context
    try:
        result = await _send_with_client(session, client)
    finally:
        QQBotContextManager.context.pop(session.session_id, None)

    reference = client.calls[0][1].get("message_reference")
    return result == ["plain"] and reference is not None and reference["message_id"] == "ROBOT-source"


async def _test_delete_translates_application_message_id() -> bool:
    """框架返回的 REFIDX 在调用撤回接口前须还原为 ROBOT ID。"""
    client = _FakeClient()
    _message_ids({"id": "ROBOT-delete", "ext_info": {"ref_idx": "REFIDX-delete"}})
    previous_client = QQBotContextManager.client
    QQBotContextManager.client = client
    try:
        await QQBotContextManager.delete_message(_make_session(target_group_prefix), "REFIDX-delete")
        await QQBotContextManager.delete_message(_make_session(target_group_prefix), "REFIDX-unmapped")
    finally:
        QQBotContextManager.client = previous_client
    return len(client.recalls) == 1 and client.recalls[0][1] == "ROBOT-delete"


async def _test_c2c_delete_uses_unified_api() -> bool:
    client = _FakeClient()
    previous_client = QQBotContextManager.client
    QQBotContextManager.client = client
    try:
        await QQBotContextManager.delete_message(_make_session(target_c2c_prefix), ["one", "two"])
    finally:
        QQBotContextManager.client = previous_client
    if len(client.recalls) != 2:
        Logger.error(f"Expected two unified recall calls, got {client.recalls}")
        return False
    for target, message_id, hidetip in client.recalls:
        if target.scope != "c2c" or message_id not in ("one", "two") or hidetip:
            Logger.error(f"Unexpected C2C recall call: {(target, message_id, hidetip)}")
            return False
    return True


@func_case
async def test_qqbot_modern_api(tester: Tester):
    """bots.qqbot.context: botpy 翻新接口接入测试"""
    await tester.test(_test_reply_target_scopes, "统一回复目标映射测试")
    await tester.test(_test_message_id_collection, "高层发送结果消息 ID 提取测试")
    await tester.test(_test_delete_translates_application_message_id, "应用层消息 ID 撤回映射测试")
    await tester.test(_test_c2c_delete_uses_unified_api, "C2C 统一撤回接口测试")
    await tester.test(_test_expired_reply_falls_back_to_proactive, "过期回复消息转主动消息测试")
    await tester.test(_test_passive_reply_limit_falls_back_to_proactive, "被动回复时间或次数超限转主动消息测试")
    await tester.test(_test_fallback_without_proactive_permission_is_silent, "被动回复回退无主动权限静默测试")
    await tester.test(_test_proactive_permission_denied_is_silent, "主动消息无权限静默测试")
    await tester.test(
        _test_platform_proactive_permission_result_overrides_local_reply_target,
        "平台主动消息无权限判定覆盖本地回复目标测试",
    )
    await tester.test(
        _test_proactive_permission_message_is_silent_for_unknown_code,
        "未知错误码的主动消息无权限文案静默测试",
    )
    await tester.test(
        _test_terminal_send_error_silently_aborts_without_proactive_fallback,
        "不可发送错误静默终止且不主动回退测试",
    )
    await tester.test(_test_terminal_send_error_stops_remaining_message_parts, "不可发送错误终止剩余消息片段测试")
    await tester.test(_test_audio_reply_limit_falls_back_to_proactive, "音频被动回复超限转主动消息测试")
    await tester.test(_test_markdown_reply_falls_back_to_proactive, "Markdown 过期回复转主动消息测试")
    await tester.test(_test_image_reply_falls_back_to_proactive, "图片过期回复转主动消息测试")
    await tester.test(_test_plain_image_is_uploaded_before_send, "Plain 图片预上传测试")
    await tester.test(_test_audio_video_are_sent_after_the_main_message, "音视频独立预上传并在主消息后发送测试")
    await tester.test(_test_other_api_error_is_not_retried, "其他 API 错误不重试测试")
    await tester.test(_test_proactive_error_is_not_retried, "主动消息错误不重复重试测试")
    await tester.test(_test_group_mention_plain_message, "群聊普通消息 Mention 渲染测试")
    await tester.test(_test_group_mention_markdown_message, "群聊 Markdown Mention 渲染测试")
    await tester.test(_test_markdown_removes_line_break_before_at, "Markdown at 标签前换行清理测试")
    await tester.test(_test_plain_allow_parse_controls_qq_atcode, "Plain.allow_parse 逐段控制 QQ 提及解析测试")
    await tester.test(_test_s3_failure_keeps_markdown_message_sendable, "S3 失败后继续发送 Markdown 测试")
    await tester.test(_test_plain_message_preserves_ids_before_later_send_failure, "Plain 后续失败保留已发送 ID 测试")
    await tester.test(_test_private_message_uses_explicit_channel_user, "频道私信使用显式目标用户测试")
    await tester.test(_test_private_message_does_not_reuse_another_users_dm, "频道私信不复用其他用户 DM 测试")
    await tester.test(_test_private_message_client_failure_returns_empty, "私信客户端解析失败返回空消息 ID 测试")
    await tester.test(_test_group_message_reply_uses_message_reference, "普通群消息回复 ID 来源测试")
    await tester.test(_test_group_quote_uses_api_message_id, "群消息平台引用使用接口消息 ID 测试")
    return tester
