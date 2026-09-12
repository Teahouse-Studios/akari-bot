"""KOOK 消息适配器的媒体可用性单元测试。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

# KOOK 客户端在导入阶段即构造 Bot，令符占位符会被配置层解析为 None 并触发 ValueError，
# 与既有 KOOK 用例一致，此处以 Bot 替身完成导入。
with patch("khl.Bot", return_value=SimpleNamespace()):
    import bots.kook.context as kook_context
    from bots.kook.context import KOOKContextManager

from bots.kook.features import features as kook_features
from bots.kook.info import client_name, sender_prefix, target_group_prefix
from core.builtins.message.chain import MessageChain
from core.builtins.message.elements import VideoElement
from core.builtins.message.internal import Audio, Image, Plain
from core.builtins.session.info import SessionInfo
from core.i18n import Locale
from core.tester import Tester, func_case
from core.utils.session import inject_features


def _session(session_id: str) -> SessionInfo:
    """构造一个 KOOK 频道会话，并注入平台能力位。"""
    session = SessionInfo(
        target_id=f"{target_group_prefix}|123456",
        target_from=target_group_prefix,
        sender_id=f"{sender_prefix}|10001",
        sender_from=sender_prefix,
        client_name=client_name,
        session_id=session_id,
        locale=Locale("zh_cn"),
    )
    inject_features(session, kook_features)
    return session


def _channel() -> SimpleNamespace:
    """构造带 send 接口的 KOOK Channel 替身。"""
    return SimpleNamespace(send=AsyncMock(return_value={"msg_id": "1"}))


async def _test_unavailable_media_elements_are_skipped() -> bool:
    """媒体元素不可得时既不发送消息也不上传资源。"""
    session = _session("kook-unavailable-media")
    channel = _channel()
    kook_bot = SimpleNamespace(create_asset=AsyncMock(return_value="https://asset"))
    message = MessageChain.assign(
        [
            Image("missing-image-fixture.png"),
            Audio("missing-audio-fixture.mp3"),
            VideoElement.assign("missing-video-fixture.mp4"),
        ]
    )
    with (
        patch.object(kook_context, "bot", new=kook_bot),
        patch.object(kook_context, "get_channel", new=AsyncMock(return_value=channel)),
        patch.object(KOOKContextManager, "context", new={}),
    ):
        result = await KOOKContextManager.send_message(session, message, quote=False)
    return result == [] and channel.send.await_count == 0 and kook_bot.create_asset.await_count == 0


async def _test_unavailable_media_keeps_remaining_text() -> bool:
    """媒体元素不可得时仍发送其余文本内容。"""
    session = _session("kook-unavailable-media-text")
    channel = _channel()
    kook_bot = SimpleNamespace(create_asset=AsyncMock(return_value="https://asset"))
    message = MessageChain.assign([Plain("hello"), Image("missing-image-fixture.png")])
    with (
        patch.object(kook_context, "bot", new=kook_bot),
        patch.object(kook_context, "get_channel", new=AsyncMock(return_value=channel)),
        patch.object(KOOKContextManager, "context", new={}),
    ):
        result = await KOOKContextManager.send_message(session, message, quote=False)
    return result == ["1"] and channel.send.await_count == 1 and channel.send.await_args.args[0] == "hello"


@func_case
async def test_kook_adapter(tester: Tester):
    """KOOK 适配器跳过底层文件不可得的媒体元素。"""
    await tester.test(_test_unavailable_media_elements_are_skipped, "KOOK 不可用的媒体元素被跳过")
    await tester.test(_test_unavailable_media_keeps_remaining_text, "KOOK 媒体不可用时保留文本")
    return tester
