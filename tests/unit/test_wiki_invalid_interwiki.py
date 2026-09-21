"""wiki 站点异常提示单元测试。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from core.builtins.message.elements import PlainElement
from core.builtins.session.features import Features
from core.builtins.session.info import SessionInfo
from core.builtins.session.internal import MessageSession
from core.constants.exceptions import SessionFinished
from core.tester import func_case, Tester
from modules.wiki.utils.wikilib import InvalidWikiError, WikiLib
from modules.wiki.wiki import query_pages

INVALID_IW_MESSAGE = "站点设置的 Interwiki 无效，请联系站点管理员解决此问题。"


def _texts(message_chain) -> str:
    return "".join(x.text for x in message_chain if isinstance(x, PlainElement))


async def _query_with_invalid_wiki(inline_mode: bool) -> dict:
    session_info = await SessionInfo.assign(
        target_id=f"TEST|Group|wiki_invalid_iw_{int(inline_mode)}",
        target_from="TEST|Group",
        client_name="TEST",
        sender_id="TEST|1",
        features=Features(),
    )
    session = MessageSession(session_info=session_info)
    captured = {}

    async def _send_message(self, message_chain=None, **kwargs):
        captured["sent"] = message_chain
        raise SessionFinished

    target_stub = SimpleNamespace(api_link="https://example.com/api.php", interwikis={}, headers={}, prefix=None)

    with (
        patch.object(WikiLib, "parse_page_info", new=AsyncMock(side_effect=InvalidWikiError(INVALID_IW_MESSAGE))),
        patch("modules.wiki.wiki.WikiTargetInfo.get_by_target_id", new=AsyncMock(return_value=target_stub)),
        patch.object(MessageSession, "hold", new=AsyncMock()),
        patch.object(MessageSession, "release", new=AsyncMock()),
        patch.object(MessageSession, "send_message", new=_send_message),
    ):
        try:
            await query_pages(session, title="Test", inline_mode=inline_mode)
        except SessionFinished:
            pass
    return captured


async def _test_inline_query_reports_detail():
    captured = await _query_with_invalid_wiki(inline_mode=True)
    return "sent" in captured and INVALID_IW_MESSAGE in _texts(captured["sent"])


async def _test_command_query_reports_detail():
    captured = await _query_with_invalid_wiki(inline_mode=False)
    return "sent" in captured and INVALID_IW_MESSAGE in _texts(captured["sent"])


@func_case
async def test_wiki_invalid_interwiki(tester: Tester):
    """wiki: 站点 interwiki 无效时的提示"""
    await tester.test(_test_inline_query_reports_detail, "内联查询发出异常详情")
    await tester.test(_test_command_query_reports_detail, "命令查询发出异常详情")
    return tester
