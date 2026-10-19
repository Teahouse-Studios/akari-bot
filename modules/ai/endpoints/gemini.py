from __future__ import annotations

import httpx
import orjson

from modules.ai.tools import TOOLS
from . import base


def _gemini_tools() -> list[dict]:
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


def _data_url_to_gemini_image(data_url: str) -> dict:
    header, _, b64 = data_url.partition(",")
    media_type = header.removeprefix("data:").split(";", maxsplit=1)[0]
    return {"type": "image", "mime_type": media_type, "data": b64}


def _content_to_interactions(content: str | list | None) -> list[dict]:
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    if not content:
        return []
    parts = []
    for part in content:
        if not isinstance(part, dict):
            continue
        if part.get("type") == "text":
            parts.append({"type": "text", "text": part.get("text", "")})
        elif part.get("type") == "image_url":
            url = (part.get("image_url") or {}).get("url")
            if not url:
                continue
            if url.startswith("data:"):
                parts.append(_data_url_to_gemini_image(url))
            else:
                parts.append({"type": "image", "uri": url})
    return parts


def _messages_to_interactions(messages: list[dict]) -> tuple[str, list[dict]]:
    system: list[str] = []
    steps: list[dict] = []
    tool_names: dict[str, str] = {}
    for msg in messages:
        role = msg.get("role")
        content = msg.get("content")
        if role == "system":
            system.append(base._content_to_text(content))
        elif role == "user":
            content_parts = _content_to_interactions(content)
            if (
                content_parts
                and steps
                and steps[-1].get("type") == "function_result"
                and isinstance(steps[-1].get("result"), list)
            ):
                # 工具产出的图片会作为用户消息追加，Interactions 支持直接并入工具结果。
                steps[-1]["result"].extend(content_parts)
            else:
                steps.append({"type": "user_input", "content": content_parts})
        elif role == "assistant":
            raw_steps = msg.get("_gemini_steps")
            if raw_steps:
                # 无状态续轮需原样回传 thought 签名与函数调用步骤。
                steps.extend(raw_steps)
                for raw_step in raw_steps:
                    if isinstance(raw_step, dict) and raw_step.get("type") == "function_call":
                        tool_names[raw_step.get("id", "")] = raw_step.get("name", "")
                continue
            if content:
                steps.append({"type": "model_output", "content": _content_to_interactions(content)})
            for tc in msg.get("tool_calls") or []:
                fn = tc.get("function") or {}
                arguments = fn.get("arguments") or "{}"
                try:
                    parsed_arguments = orjson.loads(arguments)
                except ValueError:
                    parsed_arguments = {}
                tool_names[tc.get("id", "")] = fn.get("name", "")
                steps.append(
                    {
                        "type": "function_call",
                        "id": tc.get("id", ""),
                        "name": fn.get("name", ""),
                        "arguments": parsed_arguments,
                    }
                )
        elif role == "tool":
            name = msg.get("name") or tool_names.get(msg.get("tool_call_id", ""))
            step = {
                "type": "function_result",
                "call_id": msg.get("tool_call_id", ""),
                "result": _content_to_interactions(content),
            }
            if name:
                step["name"] = name
            steps.append(step)
    return "\n\n".join(system), steps


def _gemini_thinking_level(effort: str | None) -> str | None:
    if not effort:
        return None
    effort = effort.lower()
    if effort in ("minimal", "low", "medium", "high"):
        return effort
    if effort in ("xhigh", "max"):
        return "high"
    return None


def _gemini_error_message(response: httpx.Response) -> str:
    return f"{response.status_code}: {response.text[:500]}"


class GeminiInteractionsEndpoint:
    def __init__(self, api_url: str, api_key: str, model_name: str, generation: dict | None = None):
        self.model_name = model_name
        self.tools = _gemini_tools()
        self.generation = generation or {}
        self.url = api_url.rstrip("/")
        if not self.url.endswith("/interactions"):
            self.url = f"{self.url}/interactions"
        self.client = httpx.AsyncClient(
            timeout=base.timeout,
            headers={"x-goog-api-key": api_key},
            follow_redirects=True,
        )

    async def create(self, messages: list[dict], tool_choice: str) -> base.ParsedResult:
        system_instruction, input_steps = _messages_to_interactions(messages)
        generation_config = {
            "max_output_tokens": base.max_tokens,
            "tool_choice": tool_choice,
        }
        temperature_value = base._resolve_temperature(self.generation)
        if temperature_value is not None:
            generation_config["temperature"] = temperature_value
        top_p_value = base._resolve_top_p(self.generation)
        if top_p_value is not None:
            generation_config["top_p"] = top_p_value
        thinking_level = _gemini_thinking_level(base._resolve_reasoning_effort(self.generation))
        if thinking_level is not None:
            generation_config["thinking_level"] = thinking_level

        payload = {
            "model": self.model_name,
            "input": input_steps,
            "store": False,
            "tools": self.tools,
            "generation_config": generation_config,
        }
        if system_instruction:
            payload["system_instruction"] = system_instruction

        response = await self.client.post(self.url, json=payload)
        if response.status_code == 429:
            raise base.GeminiInteractionRateLimitError(_gemini_error_message(response))
        if response.status_code >= 400:
            raise base.GeminiInteractionError(_gemini_error_message(response))

        data = response.json()
        if data.get("status") == "failed":
            raise base.GeminiInteractionError(f"Interaction failed: {data.get('errors') or data.get('status')}")

        usage = data.get("usage") or {}
        total_input_tokens = int(usage.get("total_input_tokens") or 0)
        cache_read_tokens = int(usage.get("total_cached_tokens") or 0)
        total_output_tokens = int(usage.get("total_output_tokens") or 0)
        total_thought_tokens = int(usage.get("total_thought_tokens") or 0)
        input_tokens = max(0, total_input_tokens - cache_read_tokens)

        text_parts = []
        tool_calls = []
        raw_tool_calls = []
        model_steps = []
        for step in data.get("steps") or []:
            if not isinstance(step, dict):
                continue
            step_type = step.get("type")
            if step_type in ("user_input", "function_result"):
                continue
            model_steps.append(step)
            if step_type == "model_output":
                content = step.get("content")
                if isinstance(content, str):
                    text_parts.append(content)
                    continue
                for part in content or []:
                    if isinstance(part, dict) and part.get("type") == "text":
                        text_parts.append(part.get("text", ""))
            elif step_type == "function_call":
                arguments = step.get("arguments") or {}
                if isinstance(arguments, str):
                    try:
                        arguments = orjson.loads(arguments)
                    except ValueError:
                        arguments = {}
                call_id = step.get("id", "")
                name = step.get("name", "")
                tool_calls.append(base.ToolCall(id=call_id, name=name, arguments=arguments))
                raw_tool_calls.append(
                    {
                        "id": call_id,
                        "type": "function",
                        "function": {"name": name, "arguments": orjson.dumps(arguments).decode("utf-8")},
                    }
                )

        text = "".join(text_parts)
        assistant_message = base._build_assistant_message(text, raw_tool_calls)
        # 无状态续轮依赖原样回传 thought 与 function_call 步骤。
        if model_steps:
            assistant_message["_gemini_steps"] = model_steps

        return base.ParsedResult(
            text=text,
            tool_calls=tool_calls,
            input_tokens=input_tokens,
            # 思考 token 单独计入用量，按输出计费。
            output_tokens=total_output_tokens + total_thought_tokens,
            cache_read_tokens=cache_read_tokens,
            cache_write_tokens=0,
            assistant_message=assistant_message,
        )
