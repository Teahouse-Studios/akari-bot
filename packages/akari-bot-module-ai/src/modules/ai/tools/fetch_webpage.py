import orjson
import trafilatura

from core.logger import Logger
from core.utils.html2text import HTML2Text
from core.utils.http import get_url, private_ip_check
from core.utils.web_render import web_render, SourceOptions

MAX_LENGTH = 16384

FETCH_FAILED_MESSAGE = (
    "Unable to fetch this URL. The page may be unreachable, blocked, or on a restricted address. "
    "Do not retry the same URL."
)
NO_CONTENT_MESSAGE = (
    "The page was fetched, but it contains no readable text. It may require a login or consist mainly of media."
)

REFERENCE_HINT = (
    "\n\n"
    "Citation format: if your answer uses information from this page, "
    "put `[ref:<url>]` immediately after the sentence it supports, "
    "replacing `<url>` with the exact `url` value above. "
    "Cite the page only if you actually used it."
)


fetch_webpage_desc = {
    "type": "function",
    "function": {
        "name": "fetch_webpage",
        "description": "Fetch a web page and return its main content as plain text, without HTML, links, or images. "
        "Use it to read a page the user linked, or to get details that a search snippet does not cover. "
        f"Content longer than {MAX_LENGTH} characters is truncated.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Full URL of the page, including `http://` or `https://`."}
            },
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
        html = await web_render.source(
            SourceOptions(url=url, raw_text=True, stealth=True, wait_until="domcontentloaded")
        )
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
            return NO_CONTENT_MESSAGE if fetched else FETCH_FAILED_MESSAGE

        result = {
            "url": url,
            "content": text[:MAX_LENGTH],
            "truncated": len(text) > MAX_LENGTH,
        }
        return orjson.dumps(result).decode("utf-8") + REFERENCE_HINT
    except Exception:
        return FETCH_FAILED_MESSAGE


__all__ = ["fetch_webpage", "fetch_webpage_desc"]
