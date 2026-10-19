"""OneBot 消息适配器的媒体可用性单元测试。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import bots.onebot.bot as onebot_bot
import bots.onebot.context as onebot_context
from bots.onebot.context import OneBotContextManager
from bots.onebot.features import features as onebot_features
from bots.onebot.info import client_name, sender_prefix, target_group_prefix
from core.builtins.message.chain import MessageChain
from core.builtins.message.elements import MentionElement, VideoElement
from core.builtins.message.internal import Audio, Image, Plain
from core.builtins.session.info import SessionInfo
from core.i18n import Locale
from core.tester import Tester, func_case
from core.utils.session import inject_features


def _session(session_id: str, bot_id: str | None = None) -> SessionInfo:
    session = SessionInfo(
        target_id=f"{target_group_prefix}|123456",
        target_from=target_group_prefix,
        sender_id=f"{sender_prefix}|10001",
        sender_from=sender_prefix,
        client_name=client_name,
        session_id=session_id,
        locale=Locale("zh_cn"),
        bot_id=bot_id,
    )
    inject_features(session, onebot_features)
    return session


def _client() -> SimpleNamespace:
    return SimpleNamespace(
        send_group_msg=AsyncMock(return_value={"message_id": 42}),
        send_private_msg=AsyncMock(return_value={"message_id": 42}),
        call_action=AsyncMock(return_value=[]),
    )


async def _test_unavailable_media_elements_are_skipped() -> bool:
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
    session = _session("onebot-unavailable-media-text")
    client = _client()
    message = MessageChain.assign([Plain("hello"), Image("missing-image-fixture.png")])
    with patch.object(onebot_context, "aiocqhttp_bot", new=client):
        result = await OneBotContextManager.send_message(session, message, quote=False)
    sent = client.send_group_msg.await_args.kwargs["message"]
    return result == ["42"] and sent.extract_plain_text() == "hello"


async def _test_self_mentions_are_filtered_from_inbound_message() -> bool:
    cases = [
        "~echo hi [CQ:at,qq=999] there",
        [
            {"type": "text", "data": {"text": "~echo hi"}},
            {"type": "at", "data": {"qq": "999"}},
            {"type": "text", "data": {"text": "there"}},
        ],
    ]
    for message in cases:
        assigned = SimpleNamespace()
        assign = AsyncMock(return_value=assigned)
        process = AsyncMock()
        event = SimpleNamespace(
            message=message,
            detail_type="group",
            group_id=123,
            user_id=222,
            self_id=999,
            message_id=456,
            sender={"nickname": "member"},
        )
        with (
            patch.object(onebot_bot, "mention_required", False),
            patch.object(onebot_bot.SessionInfo, "assign", new=assign),
            patch.object(onebot_bot.Bot, "process_message", new=process),
        ):
            await onebot_bot.message_handler(event)
        text = assign.await_args.kwargs["messages"].to_str()
        if "QQ|999" in text or "~echo hi" not in text or process.await_count != 1:
            return False
    return True


async def _test_only_self_mention_falls_back_to_help() -> bool:
    assigned = SimpleNamespace()
    assign = AsyncMock(return_value=assigned)
    process = AsyncMock()
    event = SimpleNamespace(
        message="[CQ:at,qq=999]",
        detail_type="group",
        group_id=123,
        user_id=222,
        self_id=999,
        message_id=456,
        sender={"nickname": "member"},
    )
    with (
        patch.object(onebot_bot, "mention_required", False),
        patch.object(onebot_bot.SessionInfo, "assign", new=assign),
        patch.object(onebot_bot.Bot, "process_message", new=process),
    ):
        await onebot_bot.message_handler(event)
    text = assign.await_args.kwargs["messages"].to_str()
    return "QQ|999" not in text and text.strip().endswith("help") and process.await_count == 1


async def _test_self_mentions_are_not_rendered_outbound() -> bool:
    session = _session("onebot-self-mention", bot_id="999")
    client = _client()
    message = MessageChain.assign(
        [
            Plain("hi "),
            MentionElement.assign("QQ|999"),
            Plain("<AT:QQ|999>"),
            MentionElement.assign("QQ|10001"),
            Plain(" bye"),
        ]
    )
    with patch.object(onebot_context, "aiocqhttp_bot", new=client):
        result = await OneBotContextManager.send_message(session, message, quote=False)
    sent = client.send_group_msg.await_args.kwargs["message"]
    serialized = str(sent)
    plain = sent.extract_plain_text()
    return (
        result == ["42"]
        and "[CQ:at,qq=999]" not in serialized
        and "[CQ:at,qq=10001]" in serialized
        and "hi" in plain
        and "bye" in plain
    )


async def _test_self_mention_only_message_is_not_sent() -> bool:
    session = _session("onebot-self-mention-only", bot_id="999")
    client = _client()
    message = MessageChain.assign([MentionElement.assign("QQ|999")])
    with patch.object(onebot_context, "aiocqhttp_bot", new=client):
        result = await OneBotContextManager.send_message(session, message, quote=False)
    return result == [] and client.send_group_msg.await_count == 0


@func_case
async def test_onebot_adapter(tester: Tester):
    """OneBot 适配器对不可用的媒体元素保持静默跳过。"""
    await tester.test(_test_unavailable_media_elements_are_skipped, "OneBot 不可用的媒体元素被跳过")
    await tester.test(_test_unavailable_media_keeps_remaining_text, "OneBot 媒体不可用时保留文本")
    await tester.test(_test_self_mentions_are_filtered_from_inbound_message, "OneBot 入站自身提及被过滤")
    await tester.test(_test_only_self_mention_falls_back_to_help, "OneBot 仅 @ 自己时回退到帮助")
    await tester.test(_test_self_mentions_are_not_rendered_outbound, "OneBot 出站不 @ 机器人自己")
    await tester.test(_test_self_mention_only_message_is_not_sent, "OneBot 仅提及自己时不发送空消息")
    return tester
