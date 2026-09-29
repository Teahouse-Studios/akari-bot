"""代理与 TLS 校验设置的单元测试。"""

import importlib
from types import SimpleNamespace
from unittest.mock import patch

from bots.qqbot.config import QQBotConfig
from core.config.core import CoreConfig, CoreSecretConfig
from core.tester import Tester, func_case
from core.utils import http as http_module

with patch.object(QQBotConfig, "enable", False):
    import bots.qqbot.bot as qqbot_bot


def _reload_network_module():
    import core.config.network as network

    return importlib.reload(network)


def _test_network_settings_follow_config():
    try:
        with (
            patch.object(CoreSecretConfig, "proxy", "http://127.0.0.1:7890"),
            patch.object(CoreConfig, "proxy_disable_ssl", True),
        ):
            network = _reload_network_module()
            configured = network.proxy == "http://127.0.0.1:7890" and network.ssl_verify is False
        with (
            patch.object(CoreSecretConfig, "proxy", ""),
            patch.object(CoreConfig, "proxy_disable_ssl", False),
        ):
            network = _reload_network_module()
            # 未填写代理时取到空字符串，各 SDK 需要 None 才表示直连
            unset = network.proxy is None and network.ssl_verify is True
        return configured and unset
    finally:
        _reload_network_module()


async def _test_request_url_uses_network_settings():
    captured: dict = {}

    class FakeResponse:
        status_code = 200
        text = "ok"

    class FakeClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def request(self, **kwargs):
            return FakeResponse()

    with (
        patch.object(http_module, "Info", SimpleNamespace(http_mock_enabled=False)),
        patch.object(http_module, "CoreConfig", SimpleNamespace(allow_request_private_ip=True)),
        patch.object(http_module, "proxy", "http://127.0.0.1:7890"),
        patch.object(http_module, "ssl_verify", False),
        patch.object(http_module.httpx, "AsyncClient", FakeClient),
    ):
        result = await http_module.request_url("http://127.0.0.1/proxy", "GET", attempt=1)

    return result == "ok" and captured.get("proxy") == "http://127.0.0.1:7890" and captured.get("verify") is False


def _test_qqbot_client_uses_network_settings():
    client = qqbot_bot._build_client()
    unset = client._proxy is None and client._ssl is True
    with (
        patch.object(qqbot_bot, "proxy", "http://127.0.0.1:7890"),
        patch.object(qqbot_bot, "ssl_verify", False),
    ):
        configured_client = qqbot_bot._build_client()
    configured = str(configured_client._proxy.url) == "http://127.0.0.1:7890" and configured_client._ssl is False
    return unset and configured


async def _test_discord_client_uses_network_settings():
    import discord

    import bots.discord.client as discord_client

    async def fake_login(self, token):
        return None

    if discord_client.discord_bot.http.connector is not None:
        return False
    with (
        patch.object(discord_client, "ssl_verify", False),
        patch.object(discord.Client, "login", fake_login),
    ):
        await discord_client.discord_bot.login("fake-token")

    connector = discord_client.discord_bot.http.connector
    configured = connector is not None and connector._ssl is False
    if connector is not None:
        await connector.close()
        discord_client.discord_bot.http.connector = None
    return configured


@func_case
async def test_network_proxy(tester: Tester):
    """core.config.network: 代理与 TLS 校验设置测试"""
    await tester.test(_test_network_settings_follow_config, "代理与 TLS 校验取值跟随配置测试")
    await tester.test(_test_request_url_uses_network_settings, "框架 HTTP 请求携带代理与校验设置测试")
    await tester.test(_test_qqbot_client_uses_network_settings, "QQBot 客户端携带代理与校验设置测试")
    await tester.test(_test_discord_client_uses_network_settings, "Discord 客户端携带代理与校验设置测试")
    return tester
