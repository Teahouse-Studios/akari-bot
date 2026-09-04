"""Wiki 手动章节锚点识别、摘要抑制与 WebRender 转交测试。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from core.builtins.bot import Bot
from core.builtins.message.elements import I18NContextElement, PlainElement
from core.builtins.session.info import SessionInfo
from core.builtins.session.internal import MessageSession
from core.i18n import Locale
from core.tester import func_case, Tester
from modules.wiki.utils.wikilib import PageInfo, WikiInfo, WikiLib, _has_manual_anchor
from modules.wiki.wiki import query_pages


MANUAL_ANCHOR_HTML = """
<div class="mw-parser-output">
  <p>页面引言。</p>
  <span class="anchor" id="manual_anchor"></span>
  <p>手动锚点后的段落内容。</p>
</div>
"""


def _wiki(*responses: dict) -> WikiLib:
    wiki = WikiLib("https://example.com/api.php")
    wiki.wiki_info = WikiInfo(
        api="https://example.com/api.php",
        articlepath="https://example.com/wiki/$1",
        script="https://example.com/w/index.php",
    )
    wiki.fixup_wiki_info = AsyncMock()
    wiki.get_page_body_class = AsyncMock(return_value=[])
    wiki.get_json = AsyncMock(side_effect=responses)
    return wiki


def _page_response() -> dict:
    return {
        "query": {
            "pages": {
                "1": {
                    "title": "示例页面",
                    "fullurl": "https://example.com/wiki/示例页面",
                    "templates": [],
                    "pageprops": {},
                    "revisions": [{"slots": {"main": {"*": "页面引言。"}}}],
                }
            }
        }
    }


async def _test_manual_anchor_html_match():
    return _has_manual_anchor(MANUAL_ANCHOR_HTML, "manual_anchor") and _has_manual_anchor(
        '<span class="anchor extra" id="带 空格"></span>', "带_空格"
    )


async def _test_manual_anchor_is_not_invalid_and_has_no_summary():
    wiki = _wiki(
        _page_response(),
        {"parse": {"sections": [{"anchor": "普通章节"}]}},
        {"parse": {"text": {"*": MANUAL_ANCHOR_HTML}}},
    )

    page = await wiki.parse_page_info("示例页面#manual_anchor")

    return (
        page.status
        and page.selected_section == "manual_anchor"
        and page.is_manual_anchor
        and not page.invalid_section
        and not page.desc
        and page.link == "https://example.com/wiki/示例页面%23manual_anchor"
        and wiki.get_json.await_count == 3
    )


async def _test_missing_manual_anchor_remains_invalid():
    wiki = _wiki(
        _page_response(),
        {"parse": {"sections": [{"anchor": "普通章节"}]}},
        {"parse": {"text": {"*": MANUAL_ANCHOR_HTML}}},
    )

    page = await wiki.parse_page_info("示例页面#不存在")
    return page.invalid_section and not page.is_manual_anchor


async def _test_heading_anchor_skips_manual_anchor_request():
    wiki = _wiki(
        _page_response(),
        {"parse": {"sections": [{"anchor": "普通章节"}]}},
    )

    page = await wiki.parse_page_info("示例页面#普通章节")
    return not page.invalid_section and not page.is_manual_anchor and wiki.get_json.await_count == 2


async def _test_manual_anchor_is_delegated_to_webrender():
    session_info = SessionInfo(
        target_id="TEST|Group|wiki-manual-anchor",
        target_from="TEST|Group",
        client_name="TEST",
        sender_id="TEST|1",
        locale=Locale("zh_cn"),
        support_image=True,
    )
    session = MessageSession(session_info=session_info)
    sent = []

    async def _send_message(self, message_chain=None, **kwargs):
        sent.append(message_chain)
        return SimpleNamespace()

    async def _run_background(_session, awaitable_factory, **_kwargs):
        await awaitable_factory()

    info = WikiInfo(
        api="https://example.com/api.php",
        realurl="https://example.com",
        is_allowed=True,
    )
    page = PageInfo(
        info=info,
        title="示例页面",
        link="https://example.com/wiki/示例页面%23manual_anchor",
        selected_section="manual_anchor",
        sections=["普通章节"],
        is_manual_anchor=True,
    )
    target = SimpleNamespace(
        api_link=info.api,
        interwikis={},
        headers={},
        prefix=None,
    )
    render = AsyncMock(return_value=False)

    with (
        patch.object(Bot.Info, "web_render_status", True),
        patch.object(WikiLib, "parse_page_info", new=AsyncMock(return_value=page)),
        patch("modules.wiki.wiki.WikiTargetInfo.get_by_target_id", new=AsyncMock(return_value=target)),
        patch("modules.wiki.wiki.finish_if_wiki_blocked", new=AsyncMock()),
        patch("modules.wiki.wiki.generate_screenshot_v2", new=render),
        patch("modules.wiki.wiki._start_background_with_release", new=_run_background),
        patch.object(MessageSession, "send_message", new=_send_message),
    ):
        await query_pages(session, title="示例页面#manual_anchor")

    first_message = sent[0]
    keys = [element.key for element in first_message if isinstance(element, I18NContextElement)]
    return (
        render.await_count == 1
        and render.await_args.args == (page.link,)
        and render.await_args.kwargs["section"] == "manual_anchor"
        and "wiki.message.section.rendering" in keys
        and "wiki.message.invalid_section" not in keys
        and not any(isinstance(element, PlainElement) for element in first_message)
    )


@func_case
async def test_wiki_manual_anchor(tester: Tester):
    await tester.test(_test_manual_anchor_html_match, "手动锚点 HTML 精确匹配")
    await tester.test(_test_manual_anchor_is_not_invalid_and_has_no_summary, "手动锚点不判不存在且不生成摘要")
    await tester.test(_test_missing_manual_anchor_remains_invalid, "不存在的手动锚点仍判章节不存在")
    await tester.test(_test_heading_anchor_skips_manual_anchor_request, "普通标题锚点不额外请求正文 HTML")
    await tester.test(_test_manual_anchor_is_delegated_to_webrender, "手动锚点不输出摘要并转交 WebRender")
    return tester
