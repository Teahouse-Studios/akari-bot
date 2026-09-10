import traceback

import orjson
from ddgs import DDGS

from core.config.base import CoreSecretConfig

proxy = CoreSecretConfig.proxy

REFERENCE_HINT = (
    "\n\nIf you use any of the above results as a source in your final answer, "
    "append a reference tag `[ref:<url>]` at the end of the cited content, "
    "replacing `<url>` with the exact URL of this source. "
    "Only cite the source if you actually reference it."
)

search_web_desc = {
    "type": "function",
    "function": {
        "name": "search_web",
        "description": "Search the web for up-to-date information.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search keywords."},
                "search_results": {
                    "type": "integer",
                    "description": "Number of search results.",
                    "default": 10,
                    "minimum": 1,
                    "maximum": 20,
                },
            },
            "required": ["query"],
        },
    },
}


async def search_web(query: str, search_results: int = 5):
    try:
        results = []

        with DDGS(proxy=proxy) as ddgs:
            for r in ddgs.text(
                query,
                region="wt-wt",
                safesearch="on",
                max_results=search_results,
            ):
                results.append(
                    {
                        "title": r["title"],
                        "url": r["href"],
                        "snippet": r["body"],
                    }
                )
        if len(results) == 0:
            return "No results found."

        return orjson.dumps(results).decode("utf-8") + REFERENCE_HINT
    except Exception:
        traceback.print_exc()
        return "Unable to use search engine, let user contact bot owner."


__all__ = ["search_web", "search_web_desc"]
