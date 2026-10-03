"""QQBot 适配器对 botpy 接口的接入测试。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from botpy.errors import ServerError
from botpy.message import GroupMessage
from botpy.protocol import MediaUrlResult

import bots.qqbot.context as qqbot_context
from bots.qqbot.config import QQBotConfig
from bots.qqbot.context import (
    QQBotContextManager,
    _message_ids,
    _reply_target,
    _resolve_api_message_id,
)
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
from core.i18n import Locale
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
    return (
        _message_ids({"id": "ROBOT-plain", "ext_info": {"ref_idx": "REFIDX-plain"}}) == ["REFIDX-plain"]
        and _message_ids({"id": "ROBOT-image", "ext_info": {"msg_idx": "REFIDX-image"}}) == ["REFIDX-image"]
        and _message_ids({"id": "legacy-id"}) == ["legacy-id"]
        and _message_ids({"id": "ROBOT-without-index"}) == []
        and _message_ids(None) == []
        and _resolve_api_message_id("REFIDX-plain") == "ROBOT-plain"
        and _resolve_api_message_id("REFIDX-image") == "ROBOT-image"
    )


class _FakeClient:
    def __init__(self):
        self.recalls = []

    async def recall_message(self, target, message_id, *, hidetip=False):
        self.recalls.append((target, message_id, hidetip))


class _FailingSendClient:
    def __init__(self, error: BaseException):
        self.error = error
        self.calls = []
        self.uploads = []

    async def send(self, target, **kwargs):
        self.calls.append((target.scope, target.target_id, target.message_id, dict(kwargs)))
        raise self.error

    async def upload_media(self, target, file_type, **kwargs):
        self.uploads.append((target.scope, target.target_id, file_type, kwargs))
        return {"file_info": "uploaded-image"}


class _CaptureSendClient:
    def __init__(self, raw_url: str | None = None):
        self.raw_url = raw_url
        self.calls = []
        self.raw_url_calls = []

    async def send(self, target, **kwargs):
        markdown = kwargs.get("markdown")
        if markdown is not None:
            self.calls.append(("markdown", {"content": markdown["content"], "keyboard": kwargs.get("keyboard")}))
            return {"id": "markdown"}
        self.calls.append(("plain", kwargs))
        return {"id": "plain"}

    async def upload_media(self, target, file_type, **kwargs):
        self.calls.append(("upload", {"file_type": file_type, **kwargs}))
        return {"file_info": "uploaded-image"}

    async def upload_media_url(self, target, file_type, **kwargs):
        self.raw_url_calls.append((target.scope, target.target_id, file_type, kwargs))
        if self.raw_url is None:
            raise RuntimeError("media upload response does not contain raw_url")
        return MediaUrlResult(upload={"file_info": "uploaded-image"}, raw_url=self.raw_url, ttl=100)


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
        with patch.object(qqbot_context, "_convert_qqbot_image", side_effect=lambda path: path):
            return await QQBotContextManager.send_message(session, message or MessageChain.assign("hello"))
    finally:
        QQBotContextManager.client = previous_client


async def _test_send_error_propagates_to_caller() -> bool:
    session = _make_session(target_group_prefix)
    error = ServerError("消息内容违规", status=400, code=40034006, response={"message": "消息内容违规"})
    client = _FailingSendClient(error)
    QQBotContextManager.context[session.session_id] = object()
    try:
        try:
            await _send_with_client(session, client)
        except ServerError as raised:
            return raised is error and len(client.calls) == 1
        return False
    finally:
        QQBotContextManager.context.pop(session.session_id, None)


async def _test_refused_delivery_is_silently_dropped() -> bool:
    for code, message in ((40054002, "机器人被禁言"), (40034105, "主动消息失败，无权限")):
        session = _make_session(target_group_prefix)
        client = _FailingSendClient(
            ServerError(message, status=400, code=code, response={"err_code": code, "message": message})
        )
        payload = MessageChain.assign([ImageElement.assign(__file__), ImageElement.assign(__file__)])
        QQBotContextManager.context[session.session_id] = object()
        try:
            result = await _send_with_client(session, client, payload)
        finally:
            QQBotContextManager.context.pop(session.session_id, None)
        if result != [] or len(client.calls) != 1 or len(client.uploads) != 2:
            Logger.error(f"Expected a refused delivery to stop after the first attempt: {client.calls}")
            return False
    return True


async def _test_plain_image_is_uploaded_before_send() -> bool:
    session = _make_session(target_group_prefix)
    client = _CaptureSendClient()
    message = MessageChain.assign([PlainElement.assign("hello"), ImageElement.assign(__file__)])
    result = await _send_with_client(session, client, message)
    expected = [
        ("upload", {"file_type": 1, "local_path": __file__, "srv_send_msg": False}),
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


async def _test_missing_media_elements_are_skipped() -> bool:
    session = _make_session(target_group_prefix)
    client = _CaptureSendClient()
    message = MessageChain.assign(
        [
            ImageElement.assign("missing-image-fixture.png"),
            AudioElement.assign("missing-audio-fixture.mp3"),
            VideoElement.assign("missing-video-fixture.mp4"),
        ]
    )
    with patch.object(qqbot_context, "qq_use_markdown", False):
        result = await _send_with_client(session, client, message)
    if result != [] or client.calls != []:
        Logger.error(f"Expected unavailable media to be skipped: result={result}, calls={client.calls}")
        return False
    return True


async def _test_missing_media_keeps_remaining_text() -> bool:
    session = _make_session(target_group_prefix)
    client = _CaptureSendClient()
    message = MessageChain.assign([PlainElement.assign("hello"), ImageElement.assign("missing-image-fixture.png")])
    with patch.object(qqbot_context, "qq_use_markdown", False):
        result = await _send_with_client(session, client, message)
    uploads = [call for call in client.calls if call[0] == "upload"]
    sends = [call for call in client.calls if call[0] == "plain"]
    return (
        result == ["plain"]
        and not uploads
        and [call[1].get("content") for call in sends] == ["hello"]
        and all("media" not in call[1] for call in sends)
    )


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


async def _test_markdown_keeps_content_line_breaks() -> bool:
    session = _make_session(target_group_prefix)
    session.support_markdown = True
    client = _CaptureSendClient()
    message = MessageChain.assign(MarkdownElement.assign('\r\n<qqbot-at-user id="member" />\nhello'))
    with patch.object(qqbot_context, "qq_use_markdown", True):
        result = await _send_with_client(session, client, message)
    return result == ["markdown"] and client.calls == [
        ("markdown", {"content": '\r\n<qqbot-at-user id="member" />\nhello', "keyboard": None})
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


async def _test_markdown_image_uses_sdk_raw_url() -> bool:
    session = _make_session(target_group_prefix)
    session.support_markdown = True
    client = _CaptureSendClient(raw_url="https://example.com/image.png")
    message = MessageChain.assign([PlainElement.assign("hello"), ImageElement.assign(__file__)])
    with (
        patch.object(qqbot_context, "qq_use_markdown", True),
        patch.object(ImageElement, "get_wh", new=AsyncMock(return_value=(32, 32))),
    ):
        result = await _send_with_client(session, client, message)
    if result != ["markdown"] or len(client.raw_url_calls) != 1:
        Logger.error(f"Expected one raw URL upload, got result={result}, calls={client.raw_url_calls}")
        return False
    scope, target_id, file_type, kwargs = client.raw_url_calls[0]
    content = client.calls[0][1]["content"]
    return (scope, target_id, file_type, kwargs) == (
        "group",
        "target",
        qqbot_context.MediaFileType.IMAGE,
        {"local_path": __file__},
    ) and "https://example.com/image.png?response-content-type=image%2Fjpeg" in content


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


async def _test_markdown_images_over_total_height_use_table_layout() -> bool:
    class _Storage:
        def __init__(self):
            self.index = 0

        async def upload_temp(self, file_path):
            self.index += 1
            return {"public_url": f"https://example.com/{self.index}.png"}

    session = _make_session(target_group_prefix)
    session.locale = Locale("zh_cn")
    session.support_markdown = True
    client = _CaptureSendClient()
    images = [ImageElement.assign(__file__) for _ in range(5)]
    message = MessageChain.assign([PlainElement.assign("before"), *images, PlainElement.assign("after")])
    dimensions = [(1000, 2000), (800, 1600), (600, 1200), (400, 800), (200, 400)]
    with (
        patch.object(qqbot_context, "qq_use_markdown", True),
        patch.object(qqbot_context, "_load_s3_storage", return_value=_Storage()),
        patch.object(ImageElement, "get_wh", new=AsyncMock(side_effect=dimensions)),
    ):
        result = await _send_with_client(session, client, message)
    if result != ["markdown"] or len(client.calls) != 1:
        return False
    content = client.calls[0][1]["content"]
    expected_images = [f"![text #32px #32px](https://example.com/{index}.png)" for index in range(1, 6)]
    table_lines = content[content.index("| 1 |") :].removesuffix("\nafter").splitlines()
    return (
        content.startswith("before\n图片列表：\n")
        and content.endswith("\nafter")
        and "\n\nafter" not in content
        and content.count("![text ") == 5
        and all(image in content for image in expected_images)
        and content.index(expected_images[0]) < content.index(expected_images[4])
        and table_lines[0] == "| 1 | 2 | 3 | 4 | 5 |"
        and table_lines[1] == "| --- | --- | --- | --- | --- |"
        and table_lines[2] == "| " + " | ".join(expected_images) + " |"
        and len(table_lines) == 3
    )


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
        attachments=[],
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
    """bots.qqbot.context: botpy 接口接入测试"""
    await tester.test(_test_reply_target_scopes, "统一回复目标映射测试")
    await tester.test(_test_message_id_collection, "高层发送结果消息 ID 提取测试")
    await tester.test(_test_delete_translates_application_message_id, "应用层消息 ID 撤回映射测试")
    await tester.test(_test_c2c_delete_uses_unified_api, "C2C 统一撤回接口测试")
    await tester.test(_test_send_error_propagates_to_caller, "发送失败向调用方上抛测试")
    await tester.test(_test_refused_delivery_is_silently_dropped, "平台拒绝投递时静默放弃剩余内容测试")
    await tester.test(_test_plain_image_is_uploaded_before_send, "Plain 图片预上传测试")
    await tester.test(_test_audio_video_are_sent_after_the_main_message, "音视频独立预上传并在主消息后发送测试")
    await tester.test(_test_missing_media_elements_are_skipped, "不可用媒体元素被跳过测试")
    await tester.test(_test_missing_media_keeps_remaining_text, "媒体不可用时保留文本测试")
    await tester.test(_test_group_mention_plain_message, "群聊普通消息 Mention 渲染测试")
    await tester.test(_test_group_mention_markdown_message, "群聊 Markdown Mention 渲染测试")
    await tester.test(_test_markdown_keeps_content_line_breaks, "Markdown 正文换行原样保留测试")
    await tester.test(_test_plain_allow_parse_controls_qq_atcode, "Plain.allow_parse 逐段控制 QQ 提及解析测试")
    await tester.test(_test_markdown_image_uses_sdk_raw_url, "Markdown 图片使用 SDK 临时直链测试")
    await tester.test(_test_s3_failure_keeps_markdown_message_sendable, "S3 失败后继续发送 Markdown 测试")
    await tester.test(_test_markdown_images_over_total_height_use_table_layout, "Markdown 图片总高度超限表格排版测试")
    await tester.test(_test_plain_message_preserves_ids_before_later_send_failure, "Plain 后续失败保留已发送 ID 测试")
    await tester.test(_test_private_message_uses_explicit_channel_user, "频道私信使用显式目标用户测试")
    await tester.test(_test_private_message_does_not_reuse_another_users_dm, "频道私信不复用其他用户 DM 测试")
    await tester.test(_test_private_message_client_failure_returns_empty, "私信客户端解析失败返回空消息 ID 测试")
    await tester.test(_test_group_message_reply_uses_message_reference, "普通群消息回复 ID 来源测试")
    await tester.test(_test_group_quote_uses_api_message_id, "群消息平台引用使用接口消息 ID 测试")
    return tester
