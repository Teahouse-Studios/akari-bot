"""modules.ai.tools.fetch_webpage 网页抓取单元测试。"""

import importlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import orjson

from core.constants.exceptions import ExternalException
from core.tester import func_case, Tester

fetch_webpage_module = importlib.import_module("modules.ai.tools.fetch_webpage")

URL = "https://example.test/article"
ARTICLE_HTML = """<html><head><title>Example</title><style>body{color:red}</style>
<script>var a=1;</script></head><body><nav>Home About</nav><article>
<h1>Akari Bot</h1>
<p>Akari Bot 是一个跨平台聊天机器人框架，支持多种平台适配。</p>
<p>它通过 JobQueue 在多个进程之间通信。</p>
</article></body></html>"""
JS_ONLY_HTML = '<html><body><div id="app"></div><script>render()</script></body></html>'


def _web_render_stub(html=None, error=None):
    source = AsyncMock(return_value=html) if error is None else AsyncMock(side_effect=error)
    return SimpleNamespace(source=source)


def _payload(result: str) -> dict:
    return orjson.loads(result.splitlines()[0])


async def _test_lightweight_path_is_preferred():
    render = _web_render_stub(ARTICLE_HTML)
    with (
        patch.object(fetch_webpage_module, "get_url", new=AsyncMock(return_value=ARTICLE_HTML)),
        patch.object(fetch_webpage_module, "web_render", new=render),
    ):
        result = await fetch_webpage_module.fetch_webpage(URL)
    payload = _payload(result)
    assert payload["url"] == URL
    assert "Akari Bot" in payload["content"] and "JobQueue" in payload["content"]
    assert "<" not in payload["content"]
    assert render.source.await_count == 0
    return True


async def _test_webrender_fallback_after_lightweight_failure():
    render = _web_render_stub(ARTICLE_HTML)
    with (
        patch.object(fetch_webpage_module, "get_url", new=AsyncMock(side_effect=ExternalException("Request timeout"))),
        patch.object(fetch_webpage_module, "private_ip_check", new=AsyncMock()),
        patch.object(fetch_webpage_module, "web_render", new=render),
    ):
        result = await fetch_webpage_module.fetch_webpage(URL)
    content = _payload(result)["content"]
    assert "Akari Bot" in content and "JobQueue" in content
    assert render.source.await_count == 1
    return True


async def _test_webrender_fallback_when_content_empty():
    render = _web_render_stub(ARTICLE_HTML)
    with (
        patch.object(fetch_webpage_module, "get_url", new=AsyncMock(return_value=JS_ONLY_HTML)),
        patch.object(fetch_webpage_module, "private_ip_check", new=AsyncMock()),
        patch.object(fetch_webpage_module, "web_render", new=render),
    ):
        result = await fetch_webpage_module.fetch_webpage(URL)
    assert "Akari Bot" in _payload(result)["content"]
    assert render.source.await_count == 1
    return True


async def _test_webrender_skipped_for_non_public_url():
    render = _web_render_stub(error=AssertionError("WebRender should not be used"))
    with (
        patch.object(fetch_webpage_module, "get_url", new=AsyncMock(side_effect=ValueError("private IP"))),
        patch.object(fetch_webpage_module, "private_ip_check", new=AsyncMock(side_effect=ValueError("private IP"))),
        patch.object(fetch_webpage_module, "web_render", new=render),
    ):
        result = await fetch_webpage_module.fetch_webpage(URL)
    assert result == "Failed to fetch URL."
    assert render.source.await_count == 0
    return True


async def _test_no_content_reports_message():
    render = _web_render_stub(JS_ONLY_HTML)
    with (
        patch.object(fetch_webpage_module, "get_url", new=AsyncMock(return_value=JS_ONLY_HTML)),
        patch.object(fetch_webpage_module, "private_ip_check", new=AsyncMock()),
        patch.object(fetch_webpage_module, "web_render", new=render),
    ):
        result = await fetch_webpage_module.fetch_webpage(URL)
    assert result == "No content extracted."
    assert render.source.await_count == 1
    return True


@func_case
async def test_ai_fetch_webpage(tester: Tester):
    """modules.ai.tools.fetch_webpage: 轻量优先、WebRender 回退与正文清洗测试"""
    await tester.test(_test_lightweight_path_is_preferred, "优先使用内置 HTTP 请求")
    await tester.test(_test_webrender_fallback_after_lightweight_failure, "轻量请求失败后回退 WebRender")
    await tester.test(_test_webrender_fallback_when_content_empty, "轻量请求无正文时回退 WebRender")
    await tester.test(_test_webrender_skipped_for_non_public_url, "非公网地址不回退 WebRender")
    await tester.test(_test_no_content_reports_message, "两条路径均无正文时返回提示")
    return tester
