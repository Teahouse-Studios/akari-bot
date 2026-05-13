import traceback

import orjson
from ddgs import DDGS

from core.config import Config

proxy = Config("proxy", cfg_type=str, secret=True)


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

        return orjson.dumps(results).decode("utf-8")
    except Exception:
        traceback.print_exc()
        return "Unable to use search engine. please let user contact the developer."


__all__ = ["search_web"]
