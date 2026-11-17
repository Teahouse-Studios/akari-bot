"""WebRender Mock 工具 - 为依赖无头浏览器的模块提供替身。"""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse

from core.logger import Logger

FIXTURE_DIR = Path(__file__).parent.parent.parent.parent / "tests" / "fixtures" / "webrender"

# 1x1 透明 PNG 的 base64 文本。截图类方法返回的是 base64 字符串而非二进制，
# 调用方（如 cb64imglst）会直接对其解码，故占位值必须保持同一形态。
PLACEHOLDER_PNG_B64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="


def _url_to_filename(url: str) -> str:
    url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    try:
        domain = (urlparse(url).hostname or "unknown").replace(".", "_")[:30]
    except Exception:
        domain = "unknown"
    return f"{domain}_{url_hash}.json"


def save_webrender_fixture(url: str, text: str) -> Path:
    """保存一份 WebRender 语料。

    :param url: 请求的 URL。
    :param text: 渲染得到的源码。
    :return: 保存的文件路径。
    """
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    filepath = FIXTURE_DIR / _url_to_filename(url)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump({"url": url, "text": text}, f, ensure_ascii=False, indent=2)
    return filepath


class WebRenderMock:
    """web_render 取数方法的替身管理器。"""

    SCREENSHOT_METHODS = (
        "element_screenshot",
        "page_screenshot",
        "section_screenshot",
        "legacy_screenshot",
    )
    PATCHED_METHODS = ("source", "get_raw", *SCREENSHOT_METHODS)

    _responses: dict[str, str] = {}
    _originals: dict[str, object] = {}
    _enabled = False

    @classmethod
    def register(cls, url: str, text: str):
        """注册一条 URL 到源码的映射。

        :param url: 精确的请求 URL。
        :param text: 该 URL 对应的源码。
        """
        cls._responses[url] = text

    @classmethod
    def clear(cls):
        """清除全部已注册语料。"""
        cls._responses.clear()

    @classmethod
    def get(cls, url: str) -> str | None:
        """按 URL 取回语料。

        :param url: 请求的 URL。
        :return: 对应源码，未注册时返回 None。
        """
        return cls._responses.get(url)

    @classmethod
    def is_enabled(cls) -> bool:
        return cls._enabled

    @classmethod
    def enable(cls):
        """接管 web_render 的取数方法。"""
        if cls._enabled:
            return
        from core.utils.web_render import web_render

        cls._originals = {name: getattr(web_render, name) for name in cls.PATCHED_METHODS}

        async def _mocked_source(options, *args, **kwargs):
            url = getattr(options, "url", None)
            text = cls.get(url)
            if text is None:
                Logger.warning(f"WebRenderMock: no source fixture for {url}")
            return text

        async def _mocked_get_raw(options, *args, **kwargs):
            url = getattr(options, "url", None)
            text = cls.get(url)
            if text is None:
                Logger.warning(f"WebRenderMock: no raw fixture for {url}")
                return None
            return {
                "status": 200,
                "content_type": "application/octet-stream",
                "data": base64.b64encode(text.encode("utf-8")).decode(),
            }

        async def _mocked_screenshot(options, *args, **kwargs):
            return [PLACEHOLDER_PNG_B64]

        web_render.source = _mocked_source
        web_render.get_raw = _mocked_get_raw
        for name in cls.SCREENSHOT_METHODS:
            setattr(web_render, name, _mocked_screenshot)
        cls._enabled = True

    @classmethod
    def disable(cls):
        """恢复被接管的真实方法。"""
        if not cls._enabled:
            return
        from core.utils.web_render import web_render

        for name, original in cls._originals.items():
            setattr(web_render, name, original)
        cls._originals = {}
        cls._enabled = False


def load_webrender_fixtures(fixture_dir: Path | None = None) -> int:
    """加载全部 WebRender 语料并接管 `web_render.source`。

    :param fixture_dir: 语料目录，默认为 tests/fixtures/webrender/。
    :return: 加载的语料数量。
    """
    if fixture_dir is None:
        fixture_dir = FIXTURE_DIR
    if not fixture_dir.exists():
        return 0

    count = 0
    for filepath in fixture_dir.glob("*.json"):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            url = data.get("url")
            if not url:
                continue
            WebRenderMock.register(url, data.get("text", ""))
            count += 1
        except Exception:
            continue

    if count:
        WebRenderMock.enable()
    return count


__all__ = [
    "WebRenderMock",
    "load_webrender_fixtures",
    "save_webrender_fixture",
    "FIXTURE_DIR",
]
