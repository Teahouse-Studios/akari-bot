import asyncio
from typing import Any

import orjson

from core.logger import Logger
from .execute_python_code import *
from .fetch_webpage import *
from .search_images import *
from .search_web import *

_tools = [execute_python_code_desc, fetch_webpage_desc, search_web_desc, search_images_desc]
TOOLS = [fnd for fnd in _tools if fnd]


def _split_images(fn_name: str, result: str) -> tuple[str, list[dict]]:
    if fn_name != "execute_python_code" or not result:
        return result, []
    try:
        payload = orjson.loads(result)
    except ValueError:
        return result, []
    if not isinstance(payload, dict):
        return result, []
    images = payload.pop("images", None)
    if not images:
        return result, []
    return orjson.dumps(payload).decode("utf-8"), images


def _build_image_message(images: list[dict]) -> dict:
    # 图片以独立用户消息回传，避免把 base64 塞进模型可见的工具文本。
    content = [
        {
            "type": "text",
            "text": "The following images were produced by execute_python_code. "
            "Include the matching [KE:image,path=...] code in your reply if the user should see an image:",
        }
    ]
    for image in images:
        content.append({"type": "text", "text": f"[KE:image,path={image['path']}]"})
        content.append({"type": "image_url", "image_url": {"url": image["data_url"]}})
    return {"role": "user", "content": content}


async def tool_function_calls(tool_calls, messages: list[dict[str, Any]]):
    async def execute_single_tool(tool_call):
        fn_name = tool_call.name
        args = tool_call.arguments

        Logger.info(f"Calling function: {fn_name} with args: {args}")

        try:
            if fn_name == "execute_python_code":
                result = await execute_python_code(args["code"])
            elif fn_name == "fetch_webpage":
                result = await fetch_webpage(args["url"])
            elif fn_name == "search_images":
                result = await search_images(args["query"], args.get("search_results", 5))
            elif fn_name == "search_web":
                result = await search_web(args["query"], args.get("search_results", 10))
            else:
                result = f"Unknown tool: {fn_name}"
        except Exception as e:
            result = str(e)

        return tool_call.id, fn_name, result

    tool_results = await asyncio.gather(*[execute_single_tool(tool_call) for tool_call in tool_calls])

    images = []
    for tool_call_id, fn_name, result in tool_results:
        content, tool_images = _split_images(fn_name, result)
        messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": content,
            }
        )
        images.extend(tool_images)
    if images:
        # 所有工具结果之后再追加图片，避免 user 消息夹在并行的 tool 消息之间。
        messages.append(_build_image_message(images))

    return messages
