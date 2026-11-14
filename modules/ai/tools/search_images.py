import asyncio
import traceback

import orjson
from ddgs import DDGS
from filetype import filetype

from core.config.base import CoreSecretConfig
from core.utils.http import get_url

proxy = CoreSecretConfig.proxy

IMAGE_HINT = (
    "\n\n"
    "You cannot see these images directly. Use only results whose `title` and `source_url` clearly match the subject "
    "the user asked about. If none clearly match, include no images.\n"
    "To show an image, output `[KE:image,path=<image_url>]` with the exact `image_url` value of that result. "
    "If your answer also uses information from an image's source page, "
    "put `[ref:<source_url>]` immediately after the sentence it supports."
)


search_images_desc = {
    "type": "function",
    "function": {
        "name": "search_images",
        "description": "Search the web for images of a subject. Returns results with a title, image URL, and source page URL.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Concise keywords naming the subject to find images of."},
                "search_results": {
                    "type": "integer",
                    "description": "Number of image results to return.",
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

        return orjson.dumps(results).decode("utf-8") + IMAGE_HINT
    except Exception:
        traceback.print_exc()
        return "Image search is unavailable. Tell the user to contact the bot owner."


__all__ = ["search_images", "search_images_desc"]
