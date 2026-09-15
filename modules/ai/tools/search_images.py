import asyncio
import traceback

import orjson
from ddgs import DDGS
from filetype import filetype

from core.config.base import CoreSecretConfig
from core.utils.http import get_url

proxy = CoreSecretConfig.proxy

REFERENCE_HINT = (
    "\n\n"
    "If you use this content as a source in your final answer, "
    "append a reference tag `[ref:<url>]` at the end of the cited content, "
    "replacing `<url>` with the exact URL (`source_url`) of this source. "
    "Only cite the source if you actually reference it."
)

VERIFY_HINT = (
    "\n\n"
    "One more step! "
    "Verify that the image in `thumbnail_url` matches the expectations, "
    "then use `image_url` as the final output. "
    "If you lack of visual ability, discard all of the above results."
)

search_images_desc = {
    "type": "function",
    "function": {
        "name": "search_images",
        "description": "Search the web for images matching a query.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Image search keywords."},
                "search_results": {
                    "type": "integer",
                    "description": "Number of image results.",
                    "default": 5,
                    "minimum": 1,
                    "maximum": 10,
                },
            },
            "required": ["query"],
        },
    },
}


async def search_images(query: str, search_results: int = 5):
    try:
        results = []

        with DDGS(proxy=proxy) as ddgs:
            for result in ddgs.images(
                query,
                region="wt-wt",
                safesearch="on",
                max_results=search_results * 2,
            ):
                results.append(
                    {
                        "title": result.get("title", ""),
                        "image_url": result.get("image", ""),
                        "thumbnail_url": result.get("thumbnail", ""),
                        "source_url": result.get("url", ""),
                    }
                )

        async def is_accessible(result):
            try:
                content = await get_url(
                    result["image_url"],
                    fmt="content",
                    attempt=1,
                    logging_err_resp=False,
                )
            except Exception:
                return False
            return isinstance(content, bytes) and filetype.match(content) is not None

        accessible = await asyncio.gather(*(is_accessible(result) for result in results))
        results = [result for result, is_result_accessible in zip(results, accessible) if is_result_accessible][
            :search_results
        ]

        if not results:
            return "No image results found."

        return orjson.dumps(results).decode("utf-8") + REFERENCE_HINT + VERIFY_HINT
    except Exception:
        traceback.print_exc()
        return "Unable to search for images, let user contact bot owner."


__all__ = ["search_images", "search_images_desc"]
