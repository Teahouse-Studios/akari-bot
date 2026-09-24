"""QQBot 事件传输模式配置测试。"""

from unittest.mock import patch

from bots.qqbot.config import QQBotConfig
from core.tester import Tester, func_case

with patch.object(QQBotConfig, "enable", False):
    import bots.qqbot.bot as qqbot_bot


def _test_default_transport_is_websocket() -> bool:
    with patch.object(QQBotConfig, "qq_use_webhook", False):
        client = qqbot_bot._build_client()
    return client._transport_mode == "websocket"


def _test_webhook_transport_uses_configured_endpoint() -> bool:
    with (
        patch.object(QQBotConfig, "qq_use_webhook", True),
        patch.object(QQBotConfig, "qq_webhook_host", "127.0.0.1"),
        patch.object(QQBotConfig, "qq_webhook_port", 9091),
        patch.object(QQBotConfig, "qq_webhook_path", "/qqbot"),
    ):
        client = qqbot_bot._build_client()
    return (
        client._transport_mode == "webhook"
        and client._webhook_host == "127.0.0.1"
        and client._webhook_port == 9091
        and client._webhook_path == "/qqbot"
    )


def _test_webhook_endpoint_values_are_coerced() -> bool:
    # 配置文件类型写错时只告警不报错，传给 SDK 前须转换。
    with (
        patch.object(QQBotConfig, "qq_use_webhook", True),
        patch.object(QQBotConfig, "qq_webhook_host", "0.0.0.0"),
        patch.object(QQBotConfig, "qq_webhook_port", "9092"),
        patch.object(QQBotConfig, "qq_webhook_path", "/qqbot"),
    ):
        client = qqbot_bot._build_client()
    return client._webhook_port == 9092


@func_case
async def test_qqbot_transport(tester: Tester):
    """bots.qqbot.bot: 事件传输模式配置测试"""
    await tester.test(_test_default_transport_is_websocket, "默认使用 WebSocket 传输测试")
    await tester.test(_test_webhook_transport_uses_configured_endpoint, "Webhook 传输使用配置端点测试")
    await tester.test(_test_webhook_endpoint_values_are_coerced, "Webhook 端点配置类型转换测试")
