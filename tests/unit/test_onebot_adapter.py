"""OneBot 消息适配器的媒体可用性单元测试。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import bots.onebot.context as onebot_context
from bots.onebot.context import OneBotContextManager
from bots.onebot.features import features as onebot_features
from bots.onebot.info import client_name, sender_prefix, target_group_prefix
from core.builtins.message.chain import MessageChain
from core.builtins.message.elements import VideoElement
from core.builtins.message.internal import Audio, Image, Plain
from core.builtins.session.info import SessionInfo
from core.i18n import Locale
from core.tester import Tester, func_case
from core.utils.session import inject_features


def _session(session_id: str) -> SessionInfo:
    """构造一个 OneBot 群聊会话，并注入平台能力位。"""
    session = SessionInfo(
        target_id=f"{target_group_prefix}|123456",
        target_from=target_group_prefix,
        sender_id=f"{sender_prefix}|10001",
        sender_from=sender_prefix,
        client_name=client_name,
        session_id=session_id,
        locale=Locale("zh_cn"),
    )
    inject_features(session, onebot_features)
    return session


def _client() -> SimpleNamespace:
    """构造带发送接口的 aiocqhttp 替身。"""
    return SimpleNamespace(
        send_group_msg=AsyncMock(return_value={"message_id": 42}),
        send_private_msg=AsyncMock(return_value={"message_id": 42}),
        call_action=AsyncMock(return_value=[]),
    )


async def _test_unavailable_media_elements_are_skipped() -> bool:
    """图片/音频/视频均不可得时不发送空消息。"""
    session = _session("onebot-unavailable-media")
    client = _client()
    message = MessageChain.assign(
        [
            Image("missing-image-fixture.png"),
            Audio("missing-audio-fixture.mp3"),
            VideoElement.assign("missing-video-fixture.mp4"),
        ]
    )
    with patch.object(onebot_context, "aiocqhttp_bot", new=client):
        result = await OneBotContextManager.send_message(session, message, quote=False)
    return result == [] and client.send_group_msg.await_count == 0


async def _test_unavailable_media_keeps_remaining_text() -> bool:
    """媒体元素不可得时仍发送其余文本内容。"""
    session = _session("onebot-unavailable-media-text")
    client = _client()
    message = MessageChain.assign([Plain("hello"), Image("missing-image-fixture.png")])
    with patch.object(onebot_context, "aiocqhttp_bot", new=client):
        result = await OneBotContextManager.send_message(session, message, quote=False)
    sent = client.send_group_msg.await_args.kwargs["message"]
    return result == ["42"] and sent.extract_plain_text() == "hello"


@func_case
async def test_onebot_adapter(tester: Tester):
    """OneBot 适配器对不可用的媒体元素保持静默跳过。"""
    await tester.test(_test_unavailable_media_elements_are_skipped, "OneBot 不可用的媒体元素被跳过")
    await tester.test(_test_unavailable_media_keeps_remaining_text, "OneBot 媒体不可用时保留文本")
    return tester
