from typing import Any

import orjson

from core.logger import Logger
from .current_datetime import *
from .execute_python_code import *
from .fetch_webpage import *
from .search_web import *

_tools = [current_datetime_desc, execute_python_code_desc, fetch_webpage_desc, search_web_desc]
TOOLS = [fnd for fnd in _tools if fnd]


async def execute_tool_calls(tool_calls, messages: list[dict[str, Any]]):
    for tool_call in tool_calls:
        fn_name = tool_call.function.name
        args = orjson.loads(tool_call.function.arguments)

        result = ""
        Logger.info(f"Calling function: {fn_name} with args: {args}")

        if fn_name == "current_datetime":
            result = current_datetime(args.get("timezone", "UTC"))
        if fn_name == "execute_python_code":
            result = await execute_python_code(args["code"])
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
