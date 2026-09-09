import asyncio
from typing import Any

import orjson

from core.logger import Logger
from .execute_python_code import *
from .fetch_webpage import *
from .search_web import *

_tools = [execute_python_code_desc, fetch_webpage_desc, search_web_desc]
TOOLS = [fnd for fnd in _tools if fnd]


async def tool_function_calls(tool_calls, messages: list[dict[str, Any]]):
    async def execute_single_tool(tool_call):
        fn_name = tool_call.function.name
        args = orjson.loads(tool_call.function.arguments)

        result = ""
        Logger.info(f"Calling function: {fn_name} with args: {args}")

        if fn_name == "execute_python_code":
            result = await execute_python_code(args["code"])
        elif fn_name == "fetch_webpage":
            result = await fetch_webpage(args["url"])
        elif fn_name == "search_web":
            result = await search_web(args["query"], args.get("search_results", 10))

        return tool_call.id, result

    tool_results = await asyncio.gather(
        *[execute_single_tool(tool_call) for tool_call in tool_calls], return_exceptions=True
    )

    for tool_call_id, result in tool_results:
        if isinstance(result, Exception):
            result = str(result)

        messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": result,
            }
        )

    return messages
