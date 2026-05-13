from typing import Any

import orjson

from core.logger import Logger
from .current_datetime import *
from .fetch_webpage import *
from .search_web import *

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "current_datetime",
            "description": "Get the current date, time, and day of the week.",
            "parameters": {
                "type": "object",
                "properties": {
                    "timezone": {
                        "type": "string",
                        "description": "Time zone, supports time zone identifier or UTC offset.",
                        "default": "UTC",
                    }
                },
            },
        },
    },
    {
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
    },
    {
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
                        "default": 5,
                        "minimum": 1,
                        "maximum": 10,
                    },
                },
                "required": ["query"],
            },
        },
    },
]


async def execute_tool_calls(tool_calls, messages: list[dict[str, Any]]):
    for tool_call in tool_calls:
        fn_name = tool_call.function.name
        args = orjson.loads(tool_call.function.arguments)

        result = ""
        Logger.info(f"Calling function: {fn_name} with args: {args}")

        if fn_name == "current_datetime":
            result = current_datetime(args.get("timezone", "UTC"))
        elif fn_name == "fetch_webpage":
            result = await fetch_webpage(args["url"])
        elif fn_name == "search_web":
            result = await search_web(args["query"], args.get("search_results", 5))

        messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result,
            }
        )
    return messages
