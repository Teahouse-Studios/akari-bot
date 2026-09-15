"""search_images AI 工具非图片结果过滤单元测试。"""

from io import BytesIO
from unittest.mock import AsyncMock, patch

from PIL import Image as PILImage

from core.tester import Tester, func_case
from modules.ai.tools.search_images import search_images


def _png_bytes() -> bytes:
    """生成合法 PNG 内容，用于模拟真实图片响应体。"""
    buffer = BytesIO()
    PILImage.new("RGB", (2, 2), "blue").save(buffer, format="PNG")
    return buffer.getvalue()


def _result(name: str) -> dict:
    """构造一条与 ddgs.images 输出结构一致的搜索结果。"""
    return {
        "title": name,
        "image": f"https://example.com/{name}",
        "thumbnail": f"https://example.com/{name}",
        "url": f"https://example.com/page/{name}",
        "source": "Example",
    }


class _FakeDDGS:
    """模拟 ddgs.DDGS 的上下文管理器。"""

    def __init__(self, results: list[dict]):
        self.results = results

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def images(self, *_args, **_kwargs):
        return list(self.results)


def _patched_search(results: list[dict], responses: dict[str, object]):
    """按 URL 返回预设响应体的 get_url 替身。"""

    async def fake_get_url(url, **_kwargs):
        response = responses[url]
        if isinstance(response, BaseException):
            raise response
        return response

    return (
        patch("modules.ai.tools.search_images.DDGS", return_value=_FakeDDGS(results)),
        patch("modules.ai.tools.search_images.get_url", new=AsyncMock(side_effect=fake_get_url)),
    )


async def _test_non_image_results_are_dropped() -> bool:
    """image_url 返回 HTML 或文本时，该结果不得进入工具输出。"""
    results = [_result("ok.png"), _result("html.png"), _result("text.png")]
    responses = {
        "https://example.com/ok.png": _png_bytes(),
        "https://example.com/html.png": b"<html>hotlink protection</html>",
        "https://example.com/text.png": "plain text",
    }
    ddgs_patch, url_patch = _patched_search(results, responses)
    with ddgs_patch, url_patch:
        output = await search_images("cat", search_results=3)
    return (
        "ok.png" in output
        and "html.png" not in output
        and "text.png" not in output
        and "No image results found" not in output
    )


async def _test_all_results_unavailable_returns_empty_hint() -> bool:
    """全部结果不可用或请求失败时返回无结果提示。"""
    results = [_result("blocked.png"), _result("offline.png")]
    responses = {
        "https://example.com/blocked.png": b"<html>hotlink protection</html>",
        "https://example.com/offline.png": ConnectionError("connection reset"),
    }
    ddgs_patch, url_patch = _patched_search(results, responses)
    with ddgs_patch, url_patch:
        output = await search_images("cat", search_results=3)
    return output == "No image results found."


async def _test_result_count_limit_is_applied_after_filtering() -> bool:
    """先过滤非法内容，再按 search_results 截断。"""
    results = [_result("html.png"), _result("ok1.png"), _result("ok2.png")]
    responses = {
        "https://example.com/html.png": b"<html>hotlink protection</html>",
        "https://example.com/ok1.png": _png_bytes(),
        "https://example.com/ok2.png": _png_bytes(),
    }
    ddgs_patch, url_patch = _patched_search(results, responses)
    with ddgs_patch, url_patch:
        output = await search_images("cat", search_results=1)
    return "ok1.png" in output and "ok2.png" not in output and "html.png" not in output


@func_case
async def test_search_images(tester: Tester):
    """search_images 仅返回可直接使用的图片结果。"""
    await tester.test(_test_non_image_results_are_dropped, "非图片响应体的结果被过滤")
    await tester.test(_test_all_results_unavailable_returns_empty_hint, "全部结果不可用时返回无结果提示")
    await tester.test(_test_result_count_limit_is_applied_after_filtering, "图片数量上限在过滤后生效")
    return tester
