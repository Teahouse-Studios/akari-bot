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
reasoning_effort = AiConfig.llm_reasoning_effort
temperature = AiConfig.llm_temperature
top_p = AiConfig.llm_top_p
top_logprobs = AiConfig.llm_top_logprobs
frequency_penalty = AiConfig.llm_frequency_penalty
presence_penalty = AiConfig.llm_presence_penalty


def _resolve_temperature(generation: dict) -> float | None:
    value = generation["temperature"] if "temperature" in generation else temperature
    return value if value is not None and value != 1 else None


def _resolve_top_p(generation: dict) -> float | None:
    value = generation["top_p"] if "top_p" in generation else top_p
    return value if value is not None and value != 1 else None


def _resolve_top_logprobs(generation: dict) -> int | None:
    value = generation["top_logprobs"] if "top_logprobs" in generation else top_logprobs
    # 显式 null 或负数均表示不请求对数概率。
    return value if value is not None and value >= 0 else None


def _resolve_reasoning_effort(generation: dict) -> str:
    return generation.get("reasoning_effort", reasoning_effort)


def _reasoning_state(effort: str) -> str:
    return "disabled" if effort.lower() == "none" else "enabled"


# 超时 / 限流等可重试异常，统一在 llm.py 中转为 ExternalException。
RETRYABLE_EXCEPTIONS = (
    APITimeoutError,
    RateLimitError,
    AnthropicAPITimeoutError,
    AnthropicRateLimitError,
)


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class ParsedResult:
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


def _strip_internal_keys(messages: list[dict]) -> list[dict]:
    # 历史消息会带有其他端点的内部键（如 _anthropic_blocks、_responses_reasoning），透传前需剔除。
    return [{k: v for k, v in msg.items() if not k.startswith("_")} for msg in messages]


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
            # 启用思考时 Anthropic 要求原样回传上一轮的 thinking 块，否则工具续轮报错。
            for raw in msg.get("_anthropic_blocks") or []:
                if raw.get("type") in ("thinking", "redacted_thinking"):
                    blocks.append(raw)
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


def _build_assistant_message(
    text: str,
    raw_tool_calls: list[dict],
    reasoning_content: str | None = None,
    deepseek_compat: bool = False,
    reasoning_enabled: bool = False,
) -> dict:
    message = {"role": "assistant", "content": text}

    if reasoning_content is not None:
        message["reasoning_content"] = reasoning_content
    # DeepSeek 思考模式下，工具调用轮次必须保留 reasoning_content，缺失时补空串。
    elif deepseek_compat and raw_tool_calls and reasoning_enabled:
        message["reasoning_content"] = ""

    if raw_tool_calls:
        message["tool_calls"] = raw_tool_calls

    return message


def _openai_effort(effort: str) -> str | None:
    effort = effort.lower()
    return None if effort == "none" else effort


class OpenAICompletionsEndpoint:
    def __init__(self, api_url: str, api_key: str, model_name: str, generation: dict | None = None):
        self.client = AsyncOpenAI(base_url=api_url, api_key=api_key)
        self.model_name = model_name
        self.generation = generation or {}

    async def create(self, messages: list[dict], tool_choice: str) -> ParsedResult:
        effort = _resolve_reasoning_effort(self.generation)
        reasoning_state = _reasoning_state(effort)
        kwargs = {
            "model": self.model_name,
            "messages": _strip_internal_keys(messages),
            "tool_choice": tool_choice,
            "tools": TOOLS,
            "max_completion_tokens": max_tokens,
            "frequency_penalty": frequency_penalty,
            "presence_penalty": presence_penalty,
            "timeout": timeout,
            "parallel_tool_calls": True,
        }
        temperature_value = _resolve_temperature(self.generation)
        if temperature_value is not None:
            kwargs["temperature"] = temperature_value
        top_p_value = _resolve_top_p(self.generation)
        if top_p_value is not None:
            kwargs["top_p"] = top_p_value
        top_logprobs_value = _resolve_top_logprobs(self.generation)
        if top_logprobs_value is not None:
            # Chat Completions 需同时开启 logprobs 才会返回对数概率。
            kwargs["logprobs"] = True
            kwargs["top_logprobs"] = top_logprobs_value

        is_deepseek = "deepseek" in self.model_name.lower()
        if is_deepseek:  # 兼容 DeepSeek
            kwargs["extra_body"] = {"thinking": {"type": reasoning_state}}

        resolved_effort = _openai_effort(effort)
        if resolved_effort is not None:
            kwargs["reasoning_effort"] = resolved_effort
        response = await self.client.chat.completions.create(**kwargs)
        res_msg = response.choices[0].message
        reasoning_content = getattr(res_msg, "reasoning_content", None)
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
            assistant_message=_build_assistant_message(
                res_msg.content or "",
                raw_tool_calls,
                reasoning_content=reasoning_content,
                deepseek_compat=is_deepseek,
                reasoning_enabled=reasoning_state == "enabled",
            ),
        )


class OpenAIResponsesEndpoint:
    def __init__(self, api_url: str, api_key: str, model_name: str, generation: dict | None = None):
        self.client = AsyncOpenAI(base_url=api_url, api_key=api_key)
        self.model_name = model_name
        self.tools = _responses_tools()
        self.generation = generation or {}

    async def create(self, messages: list[dict], tool_choice: str) -> ParsedResult:
        instructions, items = _messages_to_responses(messages)
        kwargs = {
            "model": self.model_name,
            "instructions": instructions,
            "input": items,
            "tool_choice": tool_choice,
            "tools": self.tools,
            "max_output_tokens": max_tokens,
            "timeout": timeout,
            "parallel_tool_calls": True,
        }
        temperature_value = _resolve_temperature(self.generation)
        if temperature_value is not None:
            kwargs["temperature"] = temperature_value
        top_p_value = _resolve_top_p(self.generation)
        if top_p_value is not None:
            kwargs["top_p"] = top_p_value
        top_logprobs_value = _resolve_top_logprobs(self.generation)
        if top_logprobs_value is not None:
            # Responses 需通过 include 声明才会返回对数概率。
            kwargs["top_logprobs"] = top_logprobs_value
            kwargs["include"] = ["message.output_text.logprobs"]
        effort = _openai_effort(_resolve_reasoning_effort(self.generation))
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
        assistant_message = _build_assistant_message(
            text,
            raw_tool_calls,
            reasoning_content="".join(reasoning_parts) or None,
        )
        # Responses API 无状态续轮依赖原样回传 reasoning 条目（含 encrypted_content）。
        if reasoning_items:
            assistant_message["_responses_reasoning"] = reasoning_items

        return ParsedResult(
            text=text,
            tool_calls=tool_calls,
            input_tokens=input_tokens,
            output_tokens=usage.output_tokens,
            cache_read_tokens=cache_read_tokens,
            cache_write_tokens=cache_write_tokens,
            assistant_message=assistant_message,
        )


def _anthropic_thinking(effort: str) -> dict | None:
    if _reasoning_state(effort) == "disabled":
        return {"type": "disabled"}
    # Anthropic 的思考预算最低 1024，且必须小于 max_tokens，否则无法启用思考。
    budget_tokens = max(1024, max_tokens // 2)
    if budget_tokens >= max_tokens:
        return None
    return {"type": "enabled", "budget_tokens": budget_tokens}


def _anthropic_effort(effort: str) -> str | None:
    # Anthropic 仅接受 low/medium/high/xhigh/max，OpenAI 的 none/minimal 需剔除。
    effort = effort.lower()
    return effort if effort in ("low", "medium", "high", "xhigh", "max") else None


class AnthropicEndpoint:
    def __init__(self, api_url: str, api_key: str, model_name: str, generation: dict | None = None):
        self.client = AsyncAnthropic(base_url=api_url, api_key=api_key)
        self.model_name = model_name
        self.tools = _anthropic_tools()
        self.generation = generation or {}

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
        effort = _resolve_reasoning_effort(self.generation)
        thinking = _anthropic_thinking(effort)
        if thinking is not None:
            kwargs["thinking"] = thinking
        resolved_effort = _anthropic_effort(effort)
        if resolved_effort is not None:
            kwargs["output_config"] = {"effort": resolved_effort}
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
        raw_anthropic_blocks = []
        for block in response.content or []:
            if hasattr(block, "model_dump"):
                raw_anthropic_blocks.append(block.model_dump(exclude_none=True))

            block_type = getattr(block, "type", None)

            if block_type == "text":
                text_parts.append(block.text)

            elif block_type == "tool_use":
                arguments = block.input or {}
                tool_calls.append(
                    ToolCall(
                        id=block.id,
                        name=block.name,
                        arguments=arguments,
                    )
                )
                raw_tool_calls.append(
                    {
                        "id": block.id,
                        "type": "function",
                        "function": {
                            "name": block.name,
                            "arguments": orjson.dumps(arguments).decode("utf-8"),
                        },
                    }
                )

        text = "".join(text_parts)
        assistant_message = _build_assistant_message(text, raw_tool_calls)
        assistant_message["_anthropic_blocks"] = raw_anthropic_blocks

        return ParsedResult(
            text=text,
            tool_calls=tool_calls,
            input_tokens=input_tokens,
            output_tokens=usage.output_tokens,
            cache_read_tokens=cache_read_tokens,
            cache_write_tokens=cache_write_tokens,
            assistant_message=assistant_message,
        )


def build_endpoint(endpoint: str, api_url: str, api_key: str, model_name: str, generation: dict | None = None):
    if endpoint == "openai-response":
        return OpenAIResponsesEndpoint(api_url, api_key, model_name, generation)
    if endpoint == "anthropic":
        return AnthropicEndpoint(api_url, api_key, model_name, generation)
    return OpenAICompletionsEndpoint(api_url, api_key, model_name, generation)
