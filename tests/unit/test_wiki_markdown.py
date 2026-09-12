"""wiki 页面摘要 Markdown 渲染测试。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from core.builtins.message.elements import MarkdownElement, PlainElement
from core.builtins.session.info import SessionInfo
from core.builtins.session.internal import MessageSession
from core.constants.exceptions import SessionFinished
from core.tester import func_case, Tester
from modules.wiki.utils.wikilib import PageInfo, WikiInfo, WikiLib
from modules.wiki.wiki import query_pages


async def _capture_page_desc(support_markdown: bool):
    """执行一次页面查询并返回摘要元素。"""
    session = MessageSession(
        session_info=SessionInfo(
            target_id=f"TEST|Group|wiki-markdown-{support_markdown}",
            target_from="TEST|Group",
            client_name="TEST",
            sender_id="TEST|1",
            support_markdown=support_markdown,
        )
    )
    captured = {}

    async def _finish(self, message_chain=None, **kwargs):
        captured["message"] = message_chain
        raise SessionFinished

    target = SimpleNamespace(
        api_link="https://example.com/api.php",
        interwikis={},
        headers={},
        prefix=None,
    )
    page = PageInfo(
        info=WikiInfo(api="https://example.com/api.php", is_allowed=True),
        title="示例页面",
        desc="第一行\n\n第二行",
    )

    with (
        patch.object(WikiLib, "parse_page_info", new=AsyncMock(return_value=page)),
        patch("modules.wiki.wiki.WikiTargetInfo.get_by_target_id", new=AsyncMock(return_value=target)),
        patch("modules.wiki.wiki.finish_if_wiki_blocked", new=AsyncMock()),
        patch.object(MessageSession, "hold", new=AsyncMock()),
        patch.object(MessageSession, "release", new=AsyncMock()),
        patch.object(MessageSession, "finish", new=_finish),
    ):
        try:
            await query_pages(session, title="示例页面")
        except SessionFinished:
            pass

    return captured["message"].values[0]


async def _test_markdown_page_desc_uses_blockquote():
    """支持 Markdown 时，摘要须逐行置于引用块内并保留兼容尾换行。"""
    element = await _capture_page_desc(support_markdown=True)
    return isinstance(element, MarkdownElement) and element.text == "> 第一行\n>\n> 第二行\n"


async def _test_plain_page_desc_is_unchanged():
    """不支持 Markdown 时，摘要须保持普通文本。"""
    element = await _capture_page_desc(support_markdown=False)
    return (
        isinstance(element, PlainElement)
        and not isinstance(element, MarkdownElement)
        and element.text == "第一行\n\n第二行"
    )


@func_case
async def test_wiki_markdown(tester: Tester):
    """wiki: 页面摘要按平台 Markdown 能力渲染"""
    await tester.test(_test_markdown_page_desc_uses_blockquote, "Markdown 摘要引用块测试")
    await tester.test(_test_plain_page_desc_is_unchanged, "纯文本摘要不套引用块测试")
    return tester
