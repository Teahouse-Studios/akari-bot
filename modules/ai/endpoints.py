from __future__ import annotations

from dataclasses import dataclass

import orjson
from anthropic import (
    APITimeoutError as AnthropicAPITimeoutError,
    RateLimitError as AnthropicRateLimitError,
    AsyncAnthropic,
)
from openai import APITimeoutError, RateLimitError, AsyncOpenAI

from modules.ai.config import AiConfig
from .tools import TOOLS

max_tokens = AiConfig.llm_max_tokens
timeout = AiConfig.llm_timeout
temperature = AiConfig.llm_temperature
top_p = AiConfig.llm_top_p
frequency_penalty = AiConfig.llm_frequency_penalty
presence_penalty = AiConfig.llm_presence_penalty

# 超时 / 限流等可重试异常，统一在 llm.py 中转为 ExternalException。
RETRYABLE_EXCEPTIONS = (
    APITimeoutError,
    RateLimitError,
    AnthropicAPITimeoutError,
    AnthropicRateLimitError,
)


@dataclass
class ToolCall:
    """统一的工具调用表示，与具体 API 无关。"""

    id: str
    name: str
    arguments: dict


@dataclass
class ParsedResult:
    """一次 LLM 调用的归一化结果。"""

    text: str
    tool_calls: list[ToolCall]
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    # 始终以 OpenAI Chat Completions 格式存储，用于历史上下文。
    assistant_message: dict


def _content_to_text(content: str | list) -> str:
    if isinstance(content, str):
        return content
    return "".join(part.get("text", "") for part in content if isinstance(part, dict) and part.get("type") == "text")


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


def _anthropic_tools() -> list[dict]:
    tools = []
    for tool in TOOLS:
        fn = tool["function"]
        tools.append(
            {
                "name": fn["name"],
                "description": fn["description"],
                "input_schema": fn["parameters"],
            }
        )
    return tools


def _data_url_to_anthropic_image(data_url: str) -> dict:
    header, _, b64 = data_url.partition(",")
    media_type = header.removeprefix("data:").split(";", maxsplit=1)[0]
    return {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}}


def _content_to_anthropic_blocks(content: str | list) -> list[dict]:
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    blocks = []
    for part in content:
        if not isinstance(part, dict):
            continue
        if part.get("type") == "text":
            blocks.append({"type": "text", "text": part.get("text", "")})
        elif part.get("type") == "image_url":
            blocks.append(_data_url_to_anthropic_image(part["image_url"]["url"]))
    return blocks


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
            instructions.append(_content_to_text(content))
        elif role == "user":
            items.append({"type": "message", "role": "user", "content": _content_to_responses_input(content)})
        elif role == "assistant":
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


def _messages_to_anthropic(messages: list[dict]) -> tuple[str, list[dict]]:
    system: list[str] = []
    anthropic_messages: list[dict] = []
    last_is_tool_result = False
    for msg in messages:
        role = msg.get("role")
        content = msg.get("content")
        if role == "system":
            system.append(_content_to_text(content))
        elif role == "user":
            anthropic_messages.append({"role": "user", "content": _content_to_anthropic_blocks(content)})
            last_is_tool_result = False
        elif role == "assistant":
            blocks = []
            if content:
                blocks.append({"type": "text", "text": content})
            for tc in msg.get("tool_calls") or []:
                blocks.append(
                    {
                        "type": "tool_use",
                        "id": tc["id"],
                        "name": tc["function"]["name"],
                        "input": orjson.loads(tc["function"]["arguments"]),
                    }
                )
            anthropic_messages.append({"role": "assistant", "content": blocks})
            last_is_tool_result = False
        elif role == "tool":
            block = {"type": "tool_result", "tool_use_id": msg["tool_call_id"], "content": content}
            # anthropic 要求 user/assistant 交替，多个并行 tool_result 需合并到同一个 user 消息。
            if last_is_tool_result:
                anthropic_messages[-1]["content"].append(block)
            else:
                anthropic_messages.append({"role": "user", "content": [block]})
            last_is_tool_result = True
    return "\n\n".join(system), anthropic_messages


def _build_assistant_message(text: str, raw_tool_calls: list[dict]) -> dict:
    message = {"role": "assistant", "content": text}
    if raw_tool_calls:
        message["tool_calls"] = raw_tool_calls
    return message


class OpenAICompletionsEndpoint:
    """OpenAI Chat Completions API（默认 endpoint）。"""

    def __init__(self, api_url: str, api_key: str, model_name: str):
        self.client = AsyncOpenAI(base_url=api_url, api_key=api_key)
        self.model_name = model_name

    async def create(self, messages: list[dict], tool_choice: str) -> ParsedResult:
        response = await self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            tool_choice=tool_choice,
            tools=TOOLS,
            max_completion_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            frequency_penalty=frequency_penalty,
            presence_penalty=presence_penalty,
            timeout=timeout,
            parallel_tool_calls=True,
        )

        res_msg = response.choices[0].message
        usage = response.usage
        prompt_details = getattr(usage, "prompt_tokens_details", None)
        cache_read_tokens = getattr(prompt_details, "cached_tokens", 0) or 0
        cache_write_tokens = getattr(prompt_details, "cache_creation_input_tokens", None)
        if not cache_write_tokens:
            cache_write_tokens = getattr(usage, "cache_creation_input_tokens", 0) or 0
        input_tokens = max(0, usage.prompt_tokens - cache_read_tokens - cache_write_tokens)

        tool_calls = [
            ToolCall(id=tc.id, name=tc.function.name, arguments=orjson.loads(tc.function.arguments))
            for tc in (res_msg.tool_calls or [])
        ]
        raw_tool_calls = [
            {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.function.name, "arguments": tc.function.arguments},
            }
            for tc in (res_msg.tool_calls or [])
        ]

        return ParsedResult(
            text=res_msg.content or "",
            tool_calls=tool_calls,
            input_tokens=input_tokens,
            output_tokens=usage.completion_tokens,
            cache_read_tokens=cache_read_tokens,
            cache_write_tokens=cache_write_tokens,
            assistant_message=_build_assistant_message(res_msg.content or "", raw_tool_calls),
        )


class OpenAIResponsesEndpoint:
    """OpenAI Responses API。"""

    def __init__(self, api_url: str, api_key: str, model_name: str):
        self.client = AsyncOpenAI(base_url=api_url, api_key=api_key)
        self.model_name = model_name
        self.tools = _responses_tools()

    async def create(self, messages: list[dict], tool_choice: str) -> ParsedResult:
        instructions, items = _messages_to_responses(messages)
        response = await self.client.responses.create(
            model=self.model_name,
            instructions=instructions,
            input=items,
            tool_choice=tool_choice,
            tools=self.tools,
            max_output_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            timeout=timeout,
            parallel_tool_calls=True,
        )

        usage = response.usage
        input_details = getattr(usage, "input_tokens_details", None)
        cache_read_tokens = getattr(input_details, "cached_tokens", 0) or 0
        cache_write_tokens = getattr(input_details, "cache_write_tokens", 0) or 0
        input_tokens = max(0, usage.input_tokens - cache_read_tokens - cache_write_tokens)

        text_parts = []
        tool_calls = []
        raw_tool_calls = []
        for item in response.output or []:
            item_type = getattr(item, "type", None)
            if item_type == "function_call":
                tool_calls.append(
                    ToolCall(id=item.call_id, name=item.name, arguments=orjson.loads(item.arguments or "{}"))
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
        return ParsedResult(
            text=text,
            tool_calls=tool_calls,
            input_tokens=input_tokens,
            output_tokens=usage.output_tokens,
            cache_read_tokens=cache_read_tokens,
            cache_write_tokens=cache_write_tokens,
            assistant_message=_build_assistant_message(text, raw_tool_calls),
        )


class AnthropicEndpoint:
    """Anthropic Messages API。"""

    def __init__(self, api_url: str, api_key: str, model_name: str):
        self.client = AsyncAnthropic(base_url=api_url, api_key=api_key)
        self.model_name = model_name
        self.tools = _anthropic_tools()

    async def create(self, messages: list[dict], tool_choice: str) -> ParsedResult:
        system, anthropic_messages = _messages_to_anthropic(messages)
        # anthropic 的 tool_choice 需为 {"type": "auto"/"none"/"any"/"tool"} 结构，而非字符串。
        kwargs = {
            "model": self.model_name,
            "max_tokens": max_tokens,
            "messages": anthropic_messages,
            "tools": self.tools,
            "tool_choice": {"type": tool_choice},
            "timeout": timeout,
        }
        if system:
            kwargs["system"] = system
        response = await self.client.messages.create(**kwargs)

        usage = response.usage
        cache_read_tokens = usage.cache_read_input_tokens or 0
        cache_write_tokens = usage.cache_creation_input_tokens or 0
        input_tokens = max(0, usage.input_tokens - cache_read_tokens - cache_write_tokens)

        text_parts = []
        tool_calls = []
        raw_tool_calls = []
        for block in response.content or []:
            block_type = getattr(block, "type", None)
            if block_type == "text":
                text_parts.append(block.text)
            elif block_type == "tool_use":
                arguments = block.input or {}
                tool_calls.append(ToolCall(id=block.id, name=block.name, arguments=arguments))
                raw_tool_calls.append(
                    {
                        "id": block.id,
                        "type": "function",
                        "function": {"name": block.name, "arguments": orjson.dumps(arguments).decode("utf-8")},
                    }
                )

        text = "".join(text_parts)
        return ParsedResult(
            text=text,
            tool_calls=tool_calls,
            input_tokens=input_tokens,
            output_tokens=usage.output_tokens,
            cache_read_tokens=cache_read_tokens,
            cache_write_tokens=cache_write_tokens,
            assistant_message=_build_assistant_message(text, raw_tool_calls),
        )


def build_endpoint(endpoint: str, api_url: str, api_key: str, model_name: str):
    if endpoint == "openai-response":
        return OpenAIResponsesEndpoint(api_url, api_key, model_name)
    if endpoint == "anthropic":
        return AnthropicEndpoint(api_url, api_key, model_name)
    return OpenAICompletionsEndpoint(api_url, api_key, model_name)
