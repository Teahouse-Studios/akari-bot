"""Discord 斜杠命令消息发送单元测试。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

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


@func_case
async def test_discord_slash_context(tester: Tester):
    """Discord 斜杠命令发送。"""
    await tester.test(_test_slash_response_renders_button_element, "ButtonFrame 渲染为斜杠响应按钮")
    return tester
