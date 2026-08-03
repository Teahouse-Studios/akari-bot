"""wiki 站点异常提示单元测试。

InvalidWikiError 的兜底分支原先把异常对象直接并入消息链，而消息链只接受消息元素，
一旦站点的 interwiki 配置有误便会在兜底处二次抛错，把本应友好的提示变成未捕获异常。

query_pages 另有一条 QueryInfo 入口，但现无调用方，且其在取 locale 时即已失配，
故此处只覆盖会话入口这条实际可达的路径。
"""

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
    """拼接消息链中的纯文本内容，便于断言异常详情是否落入消息。

    :param message_chain: 待检查的消息链或消息元素列表。
    """
    return "".join(x.text for x in message_chain if isinstance(x, PlainElement))


async def _query_with_invalid_wiki(inline_mode: bool) -> dict:
    """在页面查询抛出 InvalidWikiError 的前提下跑一遍查询，捕获发给用户的消息。

    :param inline_mode: 是否为内联查询。
    :return: 含 sent 键的字典，未发出消息时为空。
    """
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
        patch.object(MessageSession, "send_message", new=_send_message),
    ):
        try:
            await query_pages(session, title="Test", inline_mode=inline_mode)
        except SessionFinished:
            pass
    return captured


async def _test_inline_query_reports_detail():
    """内联查询遇到无效 interwiki 时应发出含异常详情的提示。"""
    captured = await _query_with_invalid_wiki(inline_mode=True)
    return "sent" in captured and INVALID_IW_MESSAGE in _texts(captured["sent"])


async def _test_command_query_reports_detail():
    """命令查询遇到无效 interwiki 时同样应发出含异常详情的提示。"""
    captured = await _query_with_invalid_wiki(inline_mode=False)
    return "sent" in captured and INVALID_IW_MESSAGE in _texts(captured["sent"])


@func_case
async def test_wiki_invalid_interwiki(tester: Tester):
    """wiki: 站点 interwiki 无效时的提示"""
    await tester.test(_test_inline_query_reports_detail, "内联查询发出异常详情")
    await tester.test(_test_command_query_reports_detail, "命令查询发出异常详情")
    return tester
