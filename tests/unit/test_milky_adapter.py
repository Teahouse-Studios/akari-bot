"""Milky 消息适配器的出站消息转换单元测试。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import bots.milky.context as milky_context
from bots.milky.context import MilkyContextManager
from bots.milky.features import features as milky_features
from bots.milky.info import client_name, sender_prefix, target_group_prefix
from bots.milky.utils import convert_chain_to_segments
from core.builtins.message.chain import MessageChain
from core.builtins.message.elements import MentionElement, VideoElement
from core.builtins.message.internal import Audio, Image, Plain
from core.builtins.session.info import SessionInfo
from core.i18n import Locale
from core.tester import Tester, func_case
from core.utils.session import inject_features


def _session(session_id: str, message_id: str | None = None) -> SessionInfo:
    """构造一个 Milky 群聊会话，并注入平台能力位。"""
    session = SessionInfo(
        target_id=f"{target_group_prefix}|123456",
        target_from=target_group_prefix,
        sender_id=f"{sender_prefix}|10001",
        sender_from=sender_prefix,
        client_name=client_name,
        session_id=session_id,
        message_id=message_id,
        locale=Locale("zh_cn"),
    )
    inject_features(session, milky_features)
    return session


def _client() -> SimpleNamespace:
    """构造带发送接口的 Milky 协议端替身。"""
    return SimpleNamespace(
        send_group_message=AsyncMock(return_value=SimpleNamespace(message_seq=42)),
        send_private_message=AsyncMock(return_value=SimpleNamespace(message_seq=42)),
    )


def _segment_types(segments: list) -> list[str]:
    """取出出站消息段的类型序列。"""
    return [segment.type for segment in segments]


async def _test_unavailable_media_elements_are_skipped() -> bool:
    """图片/音频/视频均不可得时不发送空消息。"""
    session = _session("milky-unavailable-media")
    client = _client()
    message = MessageChain.assign(
        [
            Image("missing-image-fixture.png"),
            Audio("missing-audio-fixture.mp3"),
            VideoElement.assign("missing-video-fixture.mp4"),
        ]
    )
    with patch.object(milky_context, "milky_bot", new=client):
        result = await MilkyContextManager.send_message(session, message, quote=False)
    return result == [] and client.send_group_message.await_count == 0


async def _test_unavailable_media_keeps_remaining_text() -> bool:
    """媒体元素不可得时仍发送其余文本内容。"""
    session = _session("milky-unavailable-media-text")
    client = _client()
    message = MessageChain.assign([Plain("hello"), Image("missing-image-fixture.png")])
    with patch.object(milky_context, "milky_bot", new=client):
        result = await MilkyContextManager.send_message(session, message, quote=False)
    sent = client.send_group_message.await_args.kwargs["message"]
    text = "".join(segment.data.text for segment in sent if segment.type == "text")
    return result == ["42"] and text == "hello"


async def _test_atcode_converts_to_mention_segments() -> bool:
    """统一 AT 码转换为提及段，非本平台 AT 码保留为文本。"""
    session = _session("milky-atcode")
    mention_segments = await convert_chain_to_segments(
        session, MessageChain.assign("hi <AT:QQ|10001> bye"), quote=False
    )
    all_segments = await convert_chain_to_segments(session, MessageChain.assign("<AT:QQ|all> hello"), quote=False)
    foreign_segments = await convert_chain_to_segments(session, MessageChain.assign("hi <AT:Other|7> bye"), quote=False)
    element_segments = await convert_chain_to_segments(
        session, MessageChain.assign([MentionElement.assign("QQ|10002")]), quote=False
    )
    # 相邻文本段会合并，故前后文本各自成段
    return (
        _segment_types(mention_segments) == ["text", "mention", "text"]
        and mention_segments[1].data.user_id == 10001
        and "".join(segment.data.text for segment in mention_segments if segment.type == "text") == "hi  bye"
        and _segment_types(all_segments) == ["mention_all", "text"]
        and _segment_types(foreign_segments) == ["text"]
        and foreign_segments[0].data.text == "hi <AT:Other|7> bye"
        and _segment_types(element_segments) == ["mention"]
        and element_segments[0].data.user_id == 10002
    )


async def _test_quote_uses_message_seq() -> bool:
    """引用发送时以触发消息的序列号构造回复段。"""
    session = _session("milky-quote", message_id="1024")
    session.messages = MessageChain.assign("trigger")
    segments = await convert_chain_to_segments(session, MessageChain.assign("reply"), quote=True)
    return _segment_types(segments) == ["reply", "text"] and segments[0].data.message_seq == 1024


def _group_message_event(segments: list[dict], sender_id: int = 10001) -> dict:
    """构造一个群聊消息事件。"""
    return {
        "event_type": "message_receive",
        "time": 1700000000,
        "self_id": 12345,
        "data": {
            "message_context": "group",
            "peer_id": 20001,
            "message_seq": 777,
            "sender_id": sender_id,
            "time": 1700000000,
            "segments": segments,
            "group": {"group_id": 20001, "group_name": "group", "member_count": 2, "max_member_count": 3},
            "group_member": {"user_id": sender_id, "nickname": "nick", "card": "card", "group_id": 20001},
        },
    }


async def _test_message_dispatch_builds_session() -> bool:
    """消息事件被解析为会话，并剥离指向机器人的提及。"""
    import bots.milky.bot as bot_module

    captured = {}

    async def fake_assign(**kwargs):
        captured.clear()
        captured.update(kwargs)
        return object()

    process = AsyncMock()
    event = _group_message_event(
        [
            {"type": "mention", "data": {"user_id": 12345}},
            {"type": "text", "data": {"text": " ping"}},
        ]
    )
    with (
        patch.object(bot_module, "milky_account", 12345),
        patch.object(bot_module, "enable_tos", False),
        patch.object(bot_module.SessionInfo, "assign", new=fake_assign),
        patch.object(bot_module.Bot, "process_message", new=process),
    ):
        await bot_module.dispatch_event(event)
    texts = "".join(getattr(value, "text", "") for value in captured.get("messages", []).values)
    return (
        process.await_count == 1
        and captured.get("target_id") == f"{target_group_prefix}|20001"
        and captured.get("sender_id") == f"{sender_prefix}|10001"
        and captured.get("is_private") is False
        and captured.get("message_id") == "777"
        and captured.get("sender_name") == "card"
        and captured.get("bot_id") == "12345"
        and texts == " ping"
    )


async def _test_group_message_ignored_when_not_addressed() -> bool:
    """群聊未 @ 机器人时按 mention_required 忽略，自身消息默认忽略。"""
    import bots.milky.bot as bot_module

    process = AsyncMock()
    plain_event = _group_message_event([{"type": "text", "data": {"text": "hi"}}])
    self_event = _group_message_event(
        [{"type": "mention", "data": {"user_id": 12345}}, {"type": "text", "data": {"text": " hi"}}],
        sender_id=12345,
    )
    with (
        patch.object(bot_module, "milky_account", 12345),
        patch.object(bot_module, "mention_required", True),
        patch.object(bot_module, "enable_tos", False),
        patch.object(bot_module.SessionInfo, "assign", new=AsyncMock()),
        patch.object(bot_module.Bot, "process_message", new=process),
    ):
        await bot_module.dispatch_event(plain_event)
        await bot_module.dispatch_event(self_event)
    return process.await_count == 0


async def _test_sdk_message_model_is_supported() -> bool:
    """入站消息兼容 SDK 模型形态（SSE 事件为字典，模型路径亦须可用）。"""
    from bots.milky.utils import to_message_chain
    from milky.models import parse_incoming_message

    message = parse_incoming_message(
        {
            "message_context": "group",
            "peer_id": 20001,
            "message_seq": 1,
            "sender_id": 10001,
            "time": 1700000000,
            "segments": [
                {"type": "text", "data": {"text": "hi "}},
                {"type": "mention", "data": {"user_id": 12345}},
            ],
            "group": {"group_id": 20001, "group_name": "group", "member_count": 1, "max_member_count": 2},
            "group_member": {
                "user_id": 10001,
                "nickname": "nick",
                "sex": "unknown",
                "group_id": 20001,
                "card": "",
                "title": "",
                "level": 1,
                "role": "member",
                "join_time": 0,
                "last_sent_time": 0,
            },
        }
    )
    chain = await to_message_chain(message)
    return [getattr(element, "text", None) for element in chain.values] == ["hi ", "QQ|12345"]


@func_case
async def test_milky_adapter(tester: Tester):
    """Milky 适配器的出站消息转换与会话组装。"""
    await tester.test(_test_unavailable_media_elements_are_skipped, "Milky 不可用的媒体元素被跳过")
    await tester.test(_test_unavailable_media_keeps_remaining_text, "Milky 媒体不可用时保留文本")
    await tester.test(_test_atcode_converts_to_mention_segments, "Milky AT 码转换为提及段")
    await tester.test(_test_quote_uses_message_seq, "Milky 引用使用消息序列号")
    await tester.test(_test_message_dispatch_builds_session, "Milky 消息事件组装会话")
    await tester.test(_test_group_message_ignored_when_not_addressed, "Milky 群聊未 @ 机器人时忽略")
    await tester.test(_test_sdk_message_model_is_supported, "Milky 兼容 SDK 消息模型")
    return tester
