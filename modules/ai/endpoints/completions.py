from __future__ import annotations

import orjson
from openai import AsyncOpenAI

from modules.ai.tools import TOOLS
from . import base


def _strip_internal_keys(messages: list[dict]) -> list[dict]:
    # 历史消息会带有其他端点的内部键（如 _anthropic_blocks、_responses_reasoning），透传前需剔除。
    return [{k: v for k, v in msg.items() if not k.startswith("_")} for msg in messages]


class OpenAICompletionsEndpoint:
    def __init__(self, api_url: str, api_key: str, model_name: str, generation: dict | None = None):
        self.client = AsyncOpenAI(base_url=api_url, api_key=api_key)
        self.model_name = model_name
        self.generation = generation or {}

    async def create(self, messages: list[dict], tool_choice: str) -> base.ParsedResult:
        effort = base._resolve_reasoning_effort(self.generation)
        reasoning_state = base._reasoning_state(effort)
        kwargs = {
            "model": self.model_name,
            "messages": _strip_internal_keys(messages),
            "tool_choice": tool_choice,
            "tools": TOOLS,
            "max_completion_tokens": base.max_tokens,
            "frequency_penalty": base.frequency_penalty,
            "presence_penalty": base.presence_penalty,
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
            # Chat Completions 需同时开启 logprobs 才会返回对数概率。
            kwargs["logprobs"] = True
            kwargs["top_logprobs"] = top_logprobs_value

        is_deepseek = "deepseek" in self.model_name.lower()
        if is_deepseek:  # 兼容 DeepSeek
            kwargs["extra_body"] = {"thinking": {"type": reasoning_state}}

        resolved_effort = base._openai_effort(effort)
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
            base.ToolCall(id=tc.id, name=tc.function.name, arguments=orjson.loads(tc.function.arguments))
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

        return base.ParsedResult(
            text=res_msg.content or "",
            tool_calls=tool_calls,
            input_tokens=input_tokens,
            output_tokens=usage.completion_tokens,
            cache_read_tokens=cache_read_tokens,
            cache_write_tokens=cache_write_tokens,
            assistant_message=base._build_assistant_message(
                res_msg.content or "",
                raw_tool_calls,
                reasoning_content=reasoning_content,
                deepseek_compat=is_deepseek,
                reasoning_enabled=reasoning_state == "enabled",
            ),
        )
