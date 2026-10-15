import orjson
import trafilatura

from core.logger import Logger
from core.utils.html2text import HTML2Text
from core.utils.http import get_url, private_ip_check
from core.utils.web_render import web_render, SourceOptions

MAX_LENGTH = 8192

REFERENCE_HINT = (
    "\n\n"
    "If you use this content as a source in your final answer, "
    "append a reference tag `[ref:<url>]` at the end of the cited content, "
    "replacing `<url>` with the exact URL of this source. "
    "Only cite the source if you actually reference it."
)


fetch_webpage_desc = {
    "type": "function",
    "function": {
        "name": "fetch_webpage",
        "description": "Fetch a webpage and return its readable text content.",
        "parameters": {
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
    },
}


def _to_plain_text(html: str) -> str:
    # 优先抽取正文，正文识别失败时转为无标记的纯文本，保证模型拿不到 HTML 标记。
    try:
        text = trafilatura.extract(html, include_comments=False) or ""
    except Exception as e:
        Logger.debug(f"Trafilatura extraction failed: {e}")
        text = ""
    if not text.strip():
        converter = HTML2Text(bodywidth=0)
        converter.ignore_links = True
        converter.ignore_images = True
        converter.ignore_emphasis = True
        text = converter.handle(html)
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


async def _fetch_lightweight(url: str) -> str | None:
    try:
        html = await get_url(url, timeout=5, attempt=1)
    except Exception as e:
        Logger.debug(f"Fetch failed for {url}: {e}")
        return None
    return html or None


async def _fetch_rendered(url: str) -> str | None:
    # WebRender 由机器人自身发起请求，需补做内网校验，否则会绕过 get_url 的地址限制。
    try:
        await private_ip_check(url)
    except ValueError as e:
        Logger.debug(f"WebRender fetch rejected for {url}: {e}")
        return None
    try:
        html = await web_render.source(SourceOptions(url=url, stealth=True))
    except Exception as e:
        Logger.debug(f"WebRender fetch failed for {url}: {e}")
        return None
    return html or None


async def fetch_webpage(url: str):
    try:
        fetched = False
        text = ""

        for fetch in (_fetch_lightweight, _fetch_rendered):
            html = await fetch(url)
            if not html:
                continue
            fetched = True
            text = _to_plain_text(html)
            if text:
                break

        if not text:
            return "No content extracted." if fetched else "Failed to fetch URL."

        result = {
            "url": url,
            "content": text[:MAX_LENGTH],
        }
        return orjson.dumps(result).decode("utf-8") + REFERENCE_HINT
    except Exception:
        return "Failed to fetch URL."


__all__ = ["fetch_webpage", "fetch_webpage_desc"]
