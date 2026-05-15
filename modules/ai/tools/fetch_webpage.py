import orjson
import trafilatura

from core.web_render import web_render, SourceOptions

MAX_LENGTH = 4000


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
        resp = await web_render.source(
            SourceOptions(
                url=url,
                stealth=True,
            )
        )
        if not resp:
            return "Failed to fetch URL."

        text = trafilatura.extract(resp.text)
        if not text:
            return "No content extracted."
        text = " ".join(text.split())
        result = {
            "url": url,
            "content": text[:MAX_LENGTH],
        }
        return orjson.dumps(result).decode("utf-8")
    except Exception:
        return "Failed to fetch URL."


__all__ = ["fetch_webpage", "fetch_webpage_desc"]
