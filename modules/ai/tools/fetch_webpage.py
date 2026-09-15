import orjson
import trafilatura

from core.utils.http import get_url
from core.utils.web_render import web_render, SourceOptions

MAX_LENGTH = 4096

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
        "description": "Fetch and extract webpage content.",
        "parameters": {
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
    },
}


async def fetch_webpage(url: str):
    try:
        try:
            resp = await web_render.source(
                SourceOptions(
                    url=url,
                    stealth=True,
                )
            )
            html = resp.text if resp else None
        except Exception:
            html = None

        if not html:
            html = await get_url(url)

        text = trafilatura.extract(html)
        if not text:
            return "No content extracted."
        text = " ".join(text.split())
        result = {
            "url": url,
            "content": text[:MAX_LENGTH],
        }
        return orjson.dumps(result).decode("utf-8") + REFERENCE_HINT
    except Exception:
        return "Failed to fetch URL."


__all__ = ["fetch_webpage", "fetch_webpage_desc"]
