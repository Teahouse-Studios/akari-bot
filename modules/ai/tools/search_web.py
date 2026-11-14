import traceback

import orjson
from ddgs import DDGS

from core.config.base import CoreSecretConfig

proxy = CoreSecretConfig.proxy

REFERENCE_HINT = (
    "\n\n"
    "Citation format: if your answer uses information from these results, "
    "put `[ref:<url>]` immediately after the sentence it supports, "
    "replacing `<url>` with the exact `url` value of that result, "
    "for example `... was released in 2011.[ref:https://example.com/page]`. "
    "Cite only results you actually used, and never cite a URL that is not in these results."
)


search_web_desc = {
    "type": "function",
    "function": {
        "name": "search_web",
        "description": "Search the web and return results with a title, URL, and short snippet. Use it for recent events, time-sensitive data, or facts you are not sure about.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Concise search keywords."},
                "search_results": {
                    "type": "integer",
                    "description": "Number of results to return.",
                    "default": 10,
                    "minimum": 1,
                    "maximum": 20,
                },
            },
            "required": ["query"],
        },
    },
}


async def search_web(query: str, search_results: int = 10):
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
        return "Web search is unavailable. Tell the user to contact the bot owner."


__all__ = ["search_web", "search_web_desc"]
