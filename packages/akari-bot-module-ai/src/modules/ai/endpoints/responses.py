from __future__ import annotations

import orjson
from openai import AsyncOpenAI

from modules.ai.tools import TOOLS
from . import base


def _responses_tools() -> list[dict]:
    tools = []
    for tool in TOOLS:
        fn = tool["function"]
        tools.append(
            {
                "type": "function",
                "name": fn["name"],
                "description": fn["description"],
                "parameters": fn["parameters"],
            }
        )
    return tools


def _content_to_responses_input(content: str | list) -> list[dict]:
    if isinstance(content, str):
        return [{"type": "input_text", "text": content}]
    items = []
    for part in content:
        if not isinstance(part, dict):
            continue
        if part.get("type") == "text":
            items.append({"type": "input_text", "text": part.get("text", "")})
        elif part.get("type") == "image_url":
            items.append({"type": "input_image", "image_url": part["image_url"]["url"]})
    return items


def _messages_to_responses(messages: list[dict]) -> tuple[str, list[dict]]:
    instructions: list[str] = []
    items: list[dict] = []
    for msg in messages:
        role = msg.get("role")
        content = msg.get("content")
        if role == "system":
            instructions.append(base._content_to_text(content))
        elif role == "user":
            items.append({"type": "message", "role": "user", "content": _content_to_responses_input(content)})
        elif role == "assistant":
            # 手动管理上下文时，Responses API 要求回传上一轮的 reasoning 条目，否则续轮丢失思维链。
            items.extend(msg.get("_responses_reasoning") or [])
            if content:
                items.append({"type": "message", "role": "assistant", "content": content})
            for tc in msg.get("tool_calls") or []:
                items.append(
                    {
                        "type": "function_call",
                        "call_id": tc["id"],
                        "name": tc["function"]["name"],
                        "arguments": tc["function"]["arguments"],
                    }
                )
        elif role == "tool":
            items.append({"type": "function_call_output", "call_id": msg["tool_call_id"], "output": content})
    return "\n\n".join(instructions), items


class OpenAIResponsesEndpoint:
    def __init__(self, api_url: str, api_key: str, model_name: str, generation: dict | None = None):
        self.client = AsyncOpenAI(base_url=api_url, api_key=api_key)
        self.model_name = model_name
        self.tools = _responses_tools()
        self.generation = generation or {}

    async def create(self, messages: list[dict], tool_choice: str) -> base.ParsedResult:
        instructions, items = _messages_to_responses(messages)
        kwargs = {
            "model": self.model_name,
            "instructions": instructions,
            "input": items,
            "tool_choice": tool_choice,
            "tools": self.tools,
            "max_output_tokens": base.max_tokens,
            "timeout": base.timeout,
            "parallel_tool_calls": True,
        }
        temperature_value = base._resolve_temperature(self.generation)
        if temperature_value is not None:
            kwargs["temperature"] = temperature_value
        top_p_value = base._resolve_top_p(self.generation)
        if top_p_value is not None:
            kwargs["top_p"] = top_p_value
        top_logprobs_value = base._resolve_top_logprobs(self.generation)
        if top_logprobs_value is not None:
            # Responses 需通过 include 声明才会返回对数概率。
            kwargs["top_logprobs"] = top_logprobs_value
            kwargs["include"] = ["message.output_text.logprobs"]
        effort = base._openai_effort(base._resolve_reasoning_effort(self.generation))
        if effort is not None:
            kwargs["reasoning"] = {"effort": effort}
        response = await self.client.responses.create(**kwargs)

        usage = response.usage
        input_details = getattr(usage, "input_tokens_details", None)
        cache_read_tokens = getattr(input_details, "cached_tokens", 0) or 0
        cache_write_tokens = getattr(input_details, "cache_write_tokens", 0) or 0
        input_tokens = max(0, usage.input_tokens - cache_read_tokens - cache_write_tokens)

        text_parts = []
        tool_calls = []
        raw_tool_calls = []
        reasoning_parts = []
        reasoning_items = []
        for item in response.output or []:
            item_type = getattr(item, "type", None)

            if item_type == "reasoning":
                if hasattr(item, "model_dump"):
                    reasoning_items.append(item.model_dump(exclude_none=True))
                for part in getattr(item, "summary", None) or []:
                    if getattr(part, "type", None) == "summary_text":
                        reasoning_parts.append(part.text)
                for part in getattr(item, "content", None) or []:
                    if getattr(part, "type", None) == "reasoning_text":
                        reasoning_parts.append(part.text)

            elif item_type == "function_call":
                tool_calls.append(
                    base.ToolCall(id=item.call_id, name=item.name, arguments=orjson.loads(item.arguments or "{}"))
                )
                raw_tool_calls.append(
                    {
                        "id": item.call_id,
                        "type": "function",
                        "function": {"name": item.name, "arguments": item.arguments},
                    }
                )
            elif item_type == "message":
                for c in item.content or []:
                    if getattr(c, "type", None) in ("output_text", "text"):
                        text_parts.append(c.text)

        text = "".join(text_parts)
        assistant_message = base._build_assistant_message(
            text,
            raw_tool_calls,
            reasoning_content="".join(reasoning_parts) or None,
        )
        # Responses API 无状态续轮依赖原样回传 reasoning 条目（含 encrypted_content）。
        if reasoning_items:
            assistant_message["_responses_reasoning"] = reasoning_items

        return base.ParsedResult(
            text=text,
            tool_calls=tool_calls,
            input_tokens=input_tokens,
            output_tokens=usage.output_tokens,
            cache_read_tokens=cache_read_tokens,
            cache_write_tokens=cache_write_tokens,
            assistant_message=assistant_message,
        )
