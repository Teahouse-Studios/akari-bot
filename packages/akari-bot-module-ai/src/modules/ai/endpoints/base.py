from __future__ import annotations

from dataclasses import dataclass

import httpx
from anthropic import (
    APITimeoutError as AnthropicAPITimeoutError,
    RateLimitError as AnthropicRateLimitError,
)
from google.genai import Client as GenaiClient
from google.genai import types as genai_types
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

_GEMINI_API_VERSIONS = ("v1beta2", "v1beta", "v1alpha", "v1")


def _split_api_url(api_url: str) -> tuple[str, str]:
    url = api_url.rstrip("/")
    for version in _GEMINI_API_VERSIONS:
        if url.endswith(f"/{version}"):
            return url[: -len(version) - 1], version
    return url, "v1beta"


def create_gemini_client(api_url: str, api_key: str) -> GenaiClient:
    base_url, api_version = _split_api_url(api_url)
    return GenaiClient(
        # SDK 拒绝空密钥，不校验鉴权的自建代理会忽略该请求头。
        api_key=api_key or "-",
        http_options=genai_types.HttpOptions(
            base_url=base_url,
            api_version=api_version,
            timeout=int(timeout * 1000),
        ),
    )


def _api_error_code(exc: Exception) -> int | None:
    for attribute in ("code", "status_code"):
        value = getattr(exc, attribute, None)
        if isinstance(value, int):
            return value
    return None


def _is_timeout_error(exc: Exception) -> bool:
    return isinstance(exc, (httpx.TimeoutException, TimeoutError)) or "timeout" in type(exc).__name__.lower()


def _is_signature_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return "thought signature" in message or "thought_signature" in message


def gemini_error(exc: Exception, error_cls: type[Exception], rate_limit_cls: type[Exception]) -> Exception:
    # 超时沿用 httpx 异常，以便落入 RETRYABLE_EXCEPTIONS。
    if _is_timeout_error(exc):
        return httpx.TimeoutException(str(exc))
    if _api_error_code(exc) == 429:
        return rate_limit_cls(str(exc))
    return error_cls(str(exc))


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


_QWEN_THINKING_PREFIXES = ("qwen3", "qwen-plus", "qwen-flash")


def _supports_qwen_thinking(model_name: str) -> bool:
    # 只有混合思考模式的千问模型接受 enable_thinking，其他千问模型传入该参数会报错。
    name = model_name.lower().rsplit("/", 1)[-1]
    return name.startswith(_QWEN_THINKING_PREFIXES)


class GeminiInteractionError(RuntimeError):
    pass


class GeminiInteractionRateLimitError(GeminiInteractionError):
    pass


class GeminiGenerateContentError(RuntimeError):
    pass


class GeminiGenerateContentRateLimitError(GeminiGenerateContentError):
    pass


# 超时 / 限流等可重试异常，统一在 llm.py 中转为 ExternalException。
RETRYABLE_EXCEPTIONS = (
    APITimeoutError,
    RateLimitError,
    AnthropicAPITimeoutError,
    AnthropicRateLimitError,
    httpx.TimeoutException,
    GeminiInteractionRateLimitError,
    GeminiGenerateContentRateLimitError,
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
