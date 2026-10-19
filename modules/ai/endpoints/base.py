from __future__ import annotations

from dataclasses import dataclass

import httpx
from anthropic import (
    APITimeoutError as AnthropicAPITimeoutError,
    RateLimitError as AnthropicRateLimitError,
)
from openai import APITimeoutError, RateLimitError

from modules.ai.config import AiConfig

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


def _openai_effort(effort: str) -> str | None:
    effort = effort.lower()
    return None if effort == "none" else effort


class GeminiInteractionError(RuntimeError):
    pass


class GeminiInteractionRateLimitError(GeminiInteractionError):
    pass


# 超时 / 限流等可重试异常，统一在 llm.py 中转为 ExternalException。
RETRYABLE_EXCEPTIONS = (
    APITimeoutError,
    RateLimitError,
    AnthropicAPITimeoutError,
    AnthropicRateLimitError,
    httpx.TimeoutException,
    GeminiInteractionRateLimitError,
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


def _content_to_text(content: str | list | None) -> str:
    if isinstance(content, str):
        return content
    if not content:
        return ""
    return "".join(part.get("text", "") for part in content if isinstance(part, dict) and part.get("type") == "text")


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
