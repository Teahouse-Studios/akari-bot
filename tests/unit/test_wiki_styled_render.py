import asyncio
import base64
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from PIL import Image

from core.tester import func_case, Tester
from modules.wiki.utils.screenshot_image import _parse_target, _styled_document, generate_screenshot
from modules.wiki.utils.wikilib import WikiInfo, WikiLib
from modules.wiki.wiki import _render_preview_items


API = "https://example.org/sub/w/api.php"
LINK = "https://example.org/wiki/Test#Section"
HEAD = """<!DOCTYPE html><html lang="zh" dir="ltr"><head>
<link rel="stylesheet" href="/sub/w/load.php?modules=site.styles&amp;only=styles">
<noscript><link rel="stylesheet" href="/sub/w/load.php?modules=noscript&amp;only=styles"></noscript>
<script>window.remoteScript = true</script></head><body class="skin-timeless page-Test">"""
BODY = """<div class="mw-parser-output"><style data-mw-deduplicate="TemplateStyles:r1">
.infobox { background: red }</style><table class="infobox"><tr><td>
<img src="/images/test.png" srcset="/images/test2.png 2x" loading="lazy" onerror="bad()">
</td></tr></table><h2 id="Section">Section</h2><p>Content</p></div>"""


def _info():
    return WikiInfo(api=API, realurl="https://example.org", articlepath="https://example.org/wiki/$1", is_allowed=True)


def _response():
    return {"parse": {"headhtml": HEAD, "text": BODY}}


def _image_data():
    data = BytesIO()
    Image.new("RGB", (2, 2), "red").save(data, "PNG")
    return [base64.b64encode(data.getvalue()).decode()]


def _test_styled_document():
    document = _styled_document(_response()["parse"], LINK)
    soup = BeautifulSoup(document, "html.parser")
    assert soup.html["lang"] == "zh" and soup.html["dir"] == "ltr"
    assert soup.body["class"] == ["skin-timeless", "page-Test"]
    assert soup.base["href"] == LINK.split("#")[0]
    stylesheet = soup.select_one('link[rel="stylesheet"]')
    assert urljoin(soup.base["href"], stylesheet["href"]) == (
        "https://example.org/sub/w/load.php?modules=site.styles&only=styles"
    )
    assert soup.select_one("#mw-content-text.mw-body-content > .mw-parser-output .infobox")
    assert soup.select_one('style[data-mw-deduplicate="TemplateStyles:r1"]')
    assert soup.select_one('head > link[href*="modules=noscript"]')
    assert not soup.script and not soup.img.has_attr("onerror") and not soup.img.has_attr("loading")
    assert urljoin(soup.base["href"], soup.img["src"]) == "https://example.org/images/test.png"
    assert soup.img["srcset"] == "/images/test2.png 2x"
    legacy = {key: {"*": value} for key, value in _response()["parse"].items()}
    assert _styled_document(legacy, LINK) == document
    return True


def _test_invalid_documents():
    for parsed in [{}, {"text": BODY}, {"text": "", "headhtml": HEAD}, {"text": BODY, "headhtml": "<html></html>"}]:
        assert _styled_document(parsed, LINK) is None
    return True


def _test_parse_targets():
    info = _info()
    info.namespaces["特殊"] = -1
    assert _parse_target(LINK, info, None) == {"page": "Test"}
    assert _parse_target("https://example.org/sub/w/index.php?curid=42", info, None) == {"pageid": 42}
    assert _parse_target("https://example.org/sub/w/index.php?title=Test", info, None) == {"page": "Test"}
    assert _parse_target(LINK, info, "Final title") == {"page": "Final title"}
    for title in ["Special:RecentChanges", "特殊:最近更改"]:
        assert _parse_target(LINK, info, title) is None
    for query in ["diff=42", "oldid=42", "action=history", "variant=zh-tw", "redirect=no"]:
        assert _parse_target(LINK.split("#")[0] + "?" + query, info, "Test") is None
    return True


async def _test_styled_screenshot_options():
    info, headers = _info(), {"Accept-Language": "zh-CN"}
    calls = []

    async def get_json(wiki, **kwargs):
        assert wiki.wiki_info is info and wiki.headers == headers
        calls.append(kwargs)
        return _response()

    with (
        patch.object(WikiLib, "get_json", new=get_json),
        patch(
            "modules.wiki.utils.screenshot_image.web_render.element_screenshot",
            new=AsyncMock(return_value=_image_data()),
        ) as element,
        patch(
            "modules.wiki.utils.screenshot_image.web_render.section_screenshot",
            new=AsyncMock(return_value=_image_data()),
        ) as section,
    ):
        result = await generate_screenshot(LINK, info, title="Test", headers=headers)
        assert result and result[0].size == (2, 2)
        options = element.await_args.args[0]
        assert options.url is None and "site.styles" in options.content
        assert ".infobox" in options.element and ".diff" not in options.element
        await generate_screenshot(LINK, info, title="Test", headers=headers, content_mode=True, allow_special_page=True)
        assert element.await_args.args[0].element[0] == ".mw-body-content"
        await generate_screenshot(LINK, info, title="Test", headers=headers, section="Section", locale="zh_cn")
        options = section.await_args.args[0]
        assert options.url is None and options.section == "Section" and options.content
    assert calls[0] == {
        "action": "parse",
        "prop": "text|headhtml",
        "redirects": 1,
        "formatversion": 2,
        "page": "Test",
    }
    assert all("useskin" not in call for call in calls)
    return True


async def _test_api_failure_fallback():
    failures = [
        RuntimeError("API unavailable"),
        TimeoutError(),
        {"error": {"code": "missingtitle"}},
        {},
        {"parse": {"text": BODY}},
        {**_response(), "warnings": {"parse": "unsupported skin"}},
    ]
    for failure in failures:
        request = AsyncMock(side_effect=failure) if isinstance(failure, Exception) else AsyncMock(return_value=failure)
        with (
            patch.object(WikiLib, "get_json", new=request),
            patch(
                "modules.wiki.utils.screenshot_image.generate_screenshot_v2", new=AsyncMock(return_value=["fallback"])
            ) as render,
        ):
            result = await generate_screenshot(LINK, _info(), title="Test", section="Section")
        assert result == ["fallback"] and render.await_count == 1
        assert "content" not in render.await_args.kwargs and render.await_args.kwargs["section"] == "Section"
    return True


async def _test_render_failure_fallback():
    for failure in [False, RuntimeError("screenshot failed")]:
        with (
            patch.object(WikiLib, "get_json", new=AsyncMock(return_value=_response())),
            patch(
                "modules.wiki.utils.screenshot_image.generate_screenshot_v2",
                new=AsyncMock(side_effect=[failure, ["fallback"]]),
            ) as render,
        ):
            assert await generate_screenshot(LINK, _info(), title="Test") == ["fallback"]
        assert render.await_count == 2
        assert render.await_args_list[0].kwargs["content"] and "content" not in render.await_args_list[1].kwargs
    return True


async def _test_legacy_and_special_pages():
    info = _info()
    info.realurl = "https://zh.moegirl.org.cn"
    with (
        patch.object(WikiLib, "get_json", new=AsyncMock()) as request,
        patch(
            "modules.wiki.utils.screenshot_image.generate_screenshot_v1", new=AsyncMock(return_value=["legacy"])
        ) as legacy,
        patch(
            "modules.wiki.utils.screenshot_image.generate_screenshot_v2", new=AsyncMock(return_value=["page"])
        ) as render,
    ):
        assert await generate_screenshot(LINK, info, headers={"Test": "value"}, section="Section") == ["legacy"]
        assert legacy.await_args.args == (info.realurl, LINK, {"Test": "value"})
        assert legacy.await_args.kwargs["section"] == "Section" and not render.await_count
        assert await generate_screenshot(LINK + "?diff=1", _info(), title="Special:Diff") == ["page"]
        assert not request.await_count
    return True


async def _test_cancel_propagates():
    for cancel_in_api in (True, False):
        request = (
            AsyncMock(side_effect=asyncio.CancelledError()) if cancel_in_api else AsyncMock(return_value=_response())
        )
        with (
            patch.object(WikiLib, "get_json", new=request),
            patch(
                "modules.wiki.utils.screenshot_image.generate_screenshot_v2",
                new=AsyncMock(side_effect=asyncio.CancelledError()),
            ) as render,
        ):
            try:
                await generate_screenshot(LINK, _info(), title="Test")
            except asyncio.CancelledError:
                assert render.await_count == (0 if cancel_in_api else 1)
            else:
                return False
    return True


async def _test_preview_target():
    info = _info()
    item = {"link": LINK, "wiki_info": info, "title": "Target title", "section": "Section", "is_allowed": True}
    session = SimpleNamespace(session_info=SimpleNamespace(locale=SimpleNamespace(locale="zh_cn")))
    with patch("modules.wiki.wiki.generate_screenshot", new=AsyncMock(return_value=False)) as render:
        result = await _render_preview_items(session, [item], {}, report_failure=True)
    assert len(result) == 1
    assert render.await_args.kwargs["wiki_info"] is info
    assert render.await_args.kwargs["title"] == "Target title"
    assert render.await_args.kwargs["section"] == "Section"
    return True


@func_case
async def test_wiki_styled_render(tester: Tester):
    await tester.test(_test_styled_document, "保留样式、相对资源及页面属性，禁用脚本")
    await tester.test(_test_invalid_documents, "正文或样式入口缺失时拒绝 API 文档")
    await tester.test(_test_parse_targets, "正确定位标题与 pageid，绕过特殊页面和行为参数")
    await tester.test(_test_styled_screenshot_options, "信息框、正文和章节通过 content 渲染")
    await tester.test(_test_api_failure_fallback, "API 错误、超时与不兼容响应回退到页面截图")
    await tester.test(_test_render_failure_fallback, "空图或截图异常回退到页面截图")
    await tester.test(_test_legacy_and_special_pages, "特殊站点使用 v1，特殊页面跳过 API")
    await tester.test(_test_cancel_propagates, "任务取消不触发 fallback")
    await tester.test(_test_preview_target, "按钮预览传递目标 Wiki、标题和章节")
    return tester
