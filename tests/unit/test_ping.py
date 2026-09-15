"""ping 模块的 Markdown 排版测试。"""

from types import SimpleNamespace

from core.builtins.message.chain import MessageChain
from core.builtins.message.elements import MarkdownElement, PlainElement
from core.builtins.message.internal import Plain
from core.builtins.session.info import SessionInfo
from core.i18n import Locale
from core.tester import Tester, func_case
from modules.core.utils import _format_ping_result


def _msg(support_markdown: bool):
    return SimpleNamespace(
        session_info=SessionInfo(
            target_id="TEST|Console|ping",
            target_from="TEST",
            client_name="TEST",
            support_markdown=support_markdown,
            locale=Locale("zh_cn"),
        )
    )


def _test_markdown_ping_uses_code_block():
    result = MessageChain.assign([Plain("Pong!"), Plain("状态信息")])
    formatted = _format_ping_result(_msg(True), result)
    element = formatted.values[0]
    return (
        isinstance(element, MarkdownElement)
        and element.text == "```\nPong!\n状态信息\n```"
        and element.disable_joke
        and not element.allow_parse
    )


def _test_plain_ping_keeps_message_chain():
    result = MessageChain.assign([Plain("Pong!"), Plain("状态信息")])
    formatted = _format_ping_result(_msg(False), result)
    return formatted is result and all(isinstance(element, PlainElement) for element in formatted.values)


@func_case
async def test_ping(tester: Tester):
    """ping：按平台 Markdown 能力选择代码块或纯文本。"""
    await tester.test(_test_markdown_ping_uses_code_block, "Markdown ping 代码块测试")
    await tester.test(_test_plain_ping_keeps_message_chain, "纯文本 ping 兼容性测试")
    return tester
