from __future__ import annotations

import orjson
from anthropic import AsyncAnthropic

from modules.ai.tools import TOOLS
from . import base


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


def _messages_to_anthropic(messages: list[dict]) -> tuple[str, list[dict]]:
    system: list[str] = []
    anthropic_messages: list[dict] = []
    last_is_tool_result = False
    for msg in messages:
        role = msg.get("role")
        content = msg.get("content")
        if role == "system":
            system.append(base._content_to_text(content))
        elif role == "user":
            blocks = _content_to_anthropic_blocks(content)
            # Anthropic 要求 user/assistant 交替；工具结果之后的图片等补充消息需并入同一轮。
            if anthropic_messages and anthropic_messages[-1]["role"] == "user":
                anthropic_messages[-1]["content"].extend(blocks)
            else:
                anthropic_messages.append({"role": "user", "content": blocks})
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


def _anthropic_thinking(effort: str) -> dict | None:
    return None if base._reasoning_state(effort) == "disabled" else {"type": "adaptive"}


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

    async def create(self, messages: list[dict], tool_choice: str) -> base.ParsedResult:
        system, anthropic_messages = _messages_to_anthropic(messages)
        # anthropic 的 tool_choice 需为 {"type": "auto"/"none"/"any"/"tool"} 结构，而非字符串。
        kwargs = {
            "model": self.model_name,
            "max_tokens": base.max_tokens,
            "messages": anthropic_messages,
            "tools": self.tools,
            "tool_choice": {"type": tool_choice},
            "timeout": base.timeout,
        }
        effort = base._resolve_reasoning_effort(self.generation)
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
                    base.ToolCall(
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
        assistant_message = base._build_assistant_message(text, raw_tool_calls)
        assistant_message["_anthropic_blocks"] = raw_anthropic_blocks

        return base.ParsedResult(
            text=text,
            tool_calls=tool_calls,
            input_tokens=input_tokens,
            output_tokens=usage.output_tokens,
            cache_read_tokens=cache_read_tokens,
            cache_write_tokens=cache_write_tokens,
            assistant_message=assistant_message,
        )
