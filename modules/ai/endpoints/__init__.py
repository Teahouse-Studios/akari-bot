from __future__ import annotations

from . import base
from .anthropic import (
    AnthropicEndpoint,
    _anthropic_effort,
    _anthropic_thinking,
    _anthropic_tools,
    _content_to_anthropic_blocks,
    _data_url_to_anthropic_image,
    _messages_to_anthropic,
)
from .base import (
    RETRYABLE_EXCEPTIONS,
    GeminiInteractionError,
    GeminiInteractionRateLimitError,
    ParsedResult,
    ToolCall,
    _build_assistant_message,
    _content_to_text,
    _openai_effort,
    _reasoning_state,
    _resolve_reasoning_effort,
    _resolve_temperature,
    _resolve_top_logprobs,
    _resolve_top_p,
    frequency_penalty,
    max_tokens,
    presence_penalty,
    reasoning_effort,
    temperature,
    timeout,
    top_logprobs,
    top_p,
)
from .completions import OpenAICompletionsEndpoint, _strip_internal_keys
from .gemini import (
    GeminiInteractionsEndpoint,
    _content_to_interactions,
    _data_url_to_gemini_image,
    _gemini_error_message,
    _gemini_thinking_level,
    _gemini_tools,
    _messages_to_interactions,
)
from .responses import OpenAIResponsesEndpoint, _content_to_responses_input, _messages_to_responses, _responses_tools

__all__ = [
    "AnthropicEndpoint",
    "GeminiInteractionError",
    "GeminiInteractionRateLimitError",
    "GeminiInteractionsEndpoint",
    "OpenAICompletionsEndpoint",
    "OpenAIResponsesEndpoint",
    "ParsedResult",
    "RETRYABLE_EXCEPTIONS",
    "ToolCall",
    "_anthropic_effort",
    "_anthropic_thinking",
    "_anthropic_tools",
    "_build_assistant_message",
    "_content_to_anthropic_blocks",
    "_content_to_interactions",
    "_content_to_responses_input",
    "_content_to_text",
    "_data_url_to_anthropic_image",
    "_data_url_to_gemini_image",
    "_gemini_error_message",
    "_gemini_thinking_level",
    "_gemini_tools",
    "_messages_to_anthropic",
    "_messages_to_interactions",
    "_messages_to_responses",
    "_openai_effort",
    "_reasoning_state",
    "_resolve_reasoning_effort",
    "_resolve_temperature",
    "_resolve_top_logprobs",
    "_resolve_top_p",
    "_responses_tools",
    "_strip_internal_keys",
    "base",
    "build_endpoint",
    "frequency_penalty",
    "max_tokens",
    "presence_penalty",
    "reasoning_effort",
    "temperature",
    "timeout",
    "top_logprobs",
    "top_p",
]


def build_endpoint(endpoint: str, api_url: str, api_key: str, model_name: str, generation: dict | None = None):
    if endpoint == "openai-response":
        return OpenAIResponsesEndpoint(api_url, api_key, model_name, generation)
    if endpoint == "anthropic":
        return AnthropicEndpoint(api_url, api_key, model_name, generation)
    if endpoint == "gemini":
        return GeminiInteractionsEndpoint(api_url, api_key, model_name, generation)
    return OpenAICompletionsEndpoint(api_url, api_key, model_name, generation)
