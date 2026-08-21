"""Discord 斜杠命令消息发送单元测试。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import bots.discord.slash_context as slash_context
from bots.discord.slash_context import DiscordSlashContextManager
from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import Button, Plain
from core.builtins.session.info import SessionInfo
from core.i18n import Locale
from core.tester import Tester, func_case


async def _test_slash_response_renders_button_element():
    session = SessionInfo(
        target_id="Discord|Channel|1",
        target_from="Discord|Channel",
        client_name="Discord",
        sender_id="Discord|Client|1",
        locale=Locale("zh_cn"),
        support_button=True,
    )
    session.session_id = "discord-slash-button"
    response = SimpleNamespace(id=10)
    ctx = SimpleNamespace(respond=AsyncMock(return_value=response), send=AsyncMock())
    DiscordSlashContextManager.context[session.session_id] = ctx
    try:
        ids = await DiscordSlashContextManager.send_message(
            session,
            MessageChain.assign([Plain("hello"), Button("Docs", "https://example.com"), Button("Help", "~help")]),
        )
    finally:
        DiscordSlashContextManager.context.pop(session.session_id, None)
    view = ctx.respond.await_args.kwargs["view"]
    return (
        ids == ["10"]
        and ctx.respond.await_args.kwargs["content"] == "hello"
        and [item.label for item in view.children] == ["Docs", "Help"]
        and view.children[0].url == "https://example.com"
        and view.children[1].custom_id.startswith("akb:")
    )


async def _test_slash_send_failure_returns_empty():
    session = SessionInfo(
        target_id="Discord|Channel|1",
        target_from="Discord|Channel",
        client_name="Discord",
        sender_id="Discord|Client|1",
        locale=Locale("zh_cn"),
    )
    session.session_id = "discord-slash-send-failure"
    ctx = SimpleNamespace(respond=AsyncMock(side_effect=RuntimeError("send failed")), send=AsyncMock())
    DiscordSlashContextManager.context[session.session_id] = ctx
    try:
        try:
            result = await DiscordSlashContextManager.send_message(session, MessageChain.assign("hello"))
        except Exception:
            return False
    finally:
        DiscordSlashContextManager.context.pop(session.session_id, None)
    return result == []


async def _test_slash_preserves_ids_before_send_failure():
    session = SessionInfo(
        target_id="Discord|Channel|1",
        target_from="Discord|Channel",
        client_name="Discord",
        sender_id="Discord|Client|1",
        locale=Locale("zh_cn"),
    )
    session.session_id = "discord-slash-partial-send"
    first = SimpleNamespace(id=10)
    ctx = SimpleNamespace(
        respond=AsyncMock(return_value=first),
        send=AsyncMock(side_effect=RuntimeError("send failed")),
    )
    DiscordSlashContextManager.context[session.session_id] = ctx
    try:
        result = await DiscordSlashContextManager.send_message(session, MessageChain.assign("a" * 2001))
    finally:
        DiscordSlashContextManager.context.pop(session.session_id, None)
    return result == ["10"] and ctx.respond.await_count == 1 and ctx.send.await_count == 1


async def _test_slash_first_response_uses_original_message_id():
    class FakeInteraction:
        def __init__(self):
            self.id = 10
            self.original_response = AsyncMock(return_value=SimpleNamespace(id=20))

    session = SessionInfo(
        target_id="Discord|Channel|1",
        target_from="Discord|Channel",
        client_name="Discord",
        sender_id="Discord|Client|1",
        locale=Locale("zh_cn"),
    )
    session.session_id = "discord-slash-original-response"
    interaction = FakeInteraction()
    ctx = SimpleNamespace(respond=AsyncMock(return_value=interaction), send=AsyncMock())
    DiscordSlashContextManager.context[session.session_id] = ctx
    try:
        with patch.object(slash_context.discord, "Interaction", FakeInteraction):
            ids = await DiscordSlashContextManager.send_message(session, MessageChain.assign("hello"))
    finally:
        DiscordSlashContextManager.context.pop(session.session_id, None)
    return ids == ["20"] and interaction.original_response.await_count == 1


@func_case
async def test_discord_slash_context(tester: Tester):
    """Discord 斜杠命令发送。"""
    await tester.test(_test_slash_response_renders_button_element, "ButtonFrame 渲染为斜杠响应按钮")
    await tester.test(_test_slash_first_response_uses_original_message_id, "首次响应返回原始消息 ID")
    await tester.test(_test_slash_send_failure_returns_empty, "Discord Slash 发送异常返回空消息 ID")
    await tester.test(_test_slash_preserves_ids_before_send_failure, "Discord Slash 后续失败保留已发送 ID")
    return tester
