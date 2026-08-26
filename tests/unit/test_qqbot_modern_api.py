"""QQBot 适配器对 botpy 翻新接口的接入测试。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from botpy.errors import ServerError
from botpy.protocol import MediaSendResult

import bots.qqbot.context as qqbot_context
import bots.qqbot.bot as qqbot_bot
from bots.qqbot.context import QQBotContextManager, _message_ids, _reply_target
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
        {"id": "plain"},
        MediaSendResult(upload={"file_info": "image"}, message={"id": "image"}),
        None,
    ]
    return _message_ids(result) == ["plain", "image"]


class _FakeClient:
    def __init__(self):
        self.recalls = []

    async def recall_message(self, target, message_id, *, hidetip=False):
        self.recalls.append((target, message_id, hidetip))


class _FailingSendClient:
    def __init__(self, code: int):
        self.code = code
        self.calls = []
        self.uploads = []

    def _record(self, target, kwargs):
        self.calls.append((target.scope, target.target_id, target.message_id, dict(kwargs)))
        if len(self.calls) == 1:
            raise ServerError(
                "回复消息msg_id已过期",
                status=400,
                code=self.code,
                response={"message": "回复消息msg_id已过期", "code": self.code, "err_code": self.code},
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
    """普通群消息的 reply_id 应来自被回复消息，而不是被提及用户。"""
    message = SimpleNamespace(
        group_openid="group",
        author=SimpleNamespace(member_openid="sender", username="sender-name", member_role="member"),
        message_reference=SimpleNamespace(message_id="referenced-message"),
        mentions=[SimpleNamespace(id="mentioned-user")],
        content="hello",
        id="incoming-message",
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
        and assign.await_args.kwargs["reply_id"] == "referenced-message"
        and process_message.await_count == 1
    )


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
    await tester.test(_test_c2c_delete_uses_unified_api, "C2C 统一撤回接口测试")
    await tester.test(_test_expired_reply_falls_back_to_proactive, "过期回复消息转主动消息测试")
    await tester.test(_test_markdown_reply_falls_back_to_proactive, "Markdown 过期回复转主动消息测试")
    await tester.test(_test_image_reply_falls_back_to_proactive, "图片过期回复转主动消息测试")
    await tester.test(_test_plain_image_is_uploaded_before_send, "Plain 图片预上传测试")
    await tester.test(_test_audio_video_are_sent_after_the_main_message, "音视频独立预上传并在主消息后发送测试")
    await tester.test(_test_other_api_error_is_not_retried, "其他 API 错误不重试测试")
    await tester.test(_test_proactive_error_is_not_retried, "主动消息错误不重复重试测试")
    await tester.test(_test_group_mention_plain_message, "群聊普通消息 Mention 渲染测试")
    await tester.test(_test_group_mention_markdown_message, "群聊 Markdown Mention 渲染测试")
    await tester.test(_test_plain_allow_parse_controls_qq_atcode, "Plain.allow_parse 逐段控制 QQ 提及解析测试")
    await tester.test(_test_s3_failure_keeps_markdown_message_sendable, "S3 失败后继续发送 Markdown 测试")
    await tester.test(_test_plain_message_preserves_ids_before_later_send_failure, "Plain 后续失败保留已发送 ID 测试")
    await tester.test(_test_private_message_uses_explicit_channel_user, "频道私信使用显式目标用户测试")
    await tester.test(_test_private_message_does_not_reuse_another_users_dm, "频道私信不复用其他用户 DM 测试")
    await tester.test(_test_private_message_client_failure_returns_empty, "私信客户端解析失败返回空消息 ID 测试")
    await tester.test(_test_group_message_reply_uses_message_reference, "普通群消息回复 ID 来源测试")
    return tester
