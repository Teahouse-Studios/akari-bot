import orjson
import trafilatura

from core.web_render import web_render, SourceOptions

MAX_LENGTH = 4000


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
        return orjson.dumps(
            {
                "url": url,
                "content": text[:MAX_LENGTH],
            }
        ).decode("utf-8")
    except Exception:
        return "Failed to fetch URL."


__all__ = ["fetch_webpage"]
