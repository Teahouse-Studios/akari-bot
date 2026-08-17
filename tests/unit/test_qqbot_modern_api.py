"""QQBot 适配器对 botpy 翻新接口的接入测试。"""

from unittest.mock import patch

from botpy.errors import ServerError
from botpy.protocol import MediaSendResult

import bots.qqbot.context as qqbot_context
from bots.qqbot.context import QQBotContextManager, _message_ids, _reply_target
from bots.qqbot.info import (
    target_c2c_prefix,
    target_direct_prefix,
    target_group_prefix,
    target_guild_prefix,
)
from core.builtins.message.chain import MessageChain
from core.builtins.message.elements import ImageElement, MentionElement, PlainElement
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

    async def send_image(self, target, **kwargs):
        self._record(target, kwargs)
        return {"id": "fallback"}


class _CaptureSendClient:
    def __init__(self):
        self.calls = []

    async def send(self, target, **kwargs):
        self.calls.append(("plain", kwargs))
        return {"id": "plain"}

    async def send_markdown(self, target, content, keyboard=None):
        self.calls.append(("markdown", {"content": content, "keyboard": keyboard}))
        return {"id": "markdown"}


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
    session.tmp = {"force_markdown": "true"}
    client = _FailingSendClient(40034005)
    QQBotContextManager.context[session.session_id] = object()
    try:
        with patch.object(qqbot_context, "qq_use_markdown", True):
            result = await _send_with_client(session, client)
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
    return result == ["fallback"] and [call[2] for call in client.calls] == ["source-message", None]


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
    await tester.test(_test_other_api_error_is_not_retried, "其他 API 错误不重试测试")
    await tester.test(_test_proactive_error_is_not_retried, "主动消息错误不重复重试测试")
    await tester.test(_test_group_mention_plain_message, "群聊普通消息 Mention 渲染测试")
    await tester.test(_test_group_mention_markdown_message, "群聊 Markdown Mention 渲染测试")
    return tester
