from __future__ import annotations

import orjson

from modules.ai.tools import TOOLS
from . import base


def _gemini_tools() -> list[dict]:
    return [
        {
            "type": "function",
            "name": tool["function"]["name"],
            "description": tool["function"]["description"],
            "parameters": tool["function"]["parameters"],
        }
        for tool in TOOLS
    ]


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


def _replayable_steps(message: dict, model_name: str, replay_signatures: bool) -> list[dict]:
    raw_steps = message.get("_gemini_steps") or []
    produced_by = message.get("_gemini_model")
    # 签名由生成它的模型签发，跨模型回放会被判为无效签名，此时仅保留无签名的步骤。
    keep_signatures = replay_signatures and (not produced_by or produced_by == model_name)
    return [step for step in raw_steps if keep_signatures or step.get("type") != "thought"]


def _messages_to_interactions(
    messages: list[dict], model_name: str, replay_signatures: bool = True
) -> tuple[str, list[dict], bool]:
    system: list[str] = []
    steps: list[dict] = []
    tool_names: dict[str, str] = {}
    has_signatures = False
    for msg in messages:
        role = msg.get("role")
        content = msg.get("content")
        if role == "system":
            system.append(base._content_to_text(content))
        elif role == "user":
            content_parts = _content_to_interactions(content)
            if not content_parts:
                continue
            if steps and steps[-1].get("type") == "function_result" and isinstance(steps[-1].get("result"), list):
                # 工具产出的图片会作为用户消息追加，Interactions 支持直接并入工具结果。
                steps[-1]["result"].extend(content_parts)
            else:
                steps.append({"type": "user_input", "content": content_parts})
        elif role == "assistant":
            if msg.get("_gemini_steps"):
                # 无状态续轮需原样回传 thought 签名与函数调用步骤。
                replayed = _replayable_steps(msg, model_name, replay_signatures)
                steps.extend(replayed)
                has_signatures = has_signatures or any(step.get("type") == "thought" for step in replayed)
                for step in replayed:
                    if step.get("type") == "function_call":
                        tool_names[step.get("id", "")] = step.get("name", "")
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
    return "\n\n".join(system), steps, has_signatures


def _gemini_thinking_level(effort: str | None) -> str | None:
    if not effort:
        return None
    effort = effort.lower()
    if effort in ("minimal", "low", "medium", "high"):
        return effort
    if effort in ("xhigh", "max"):
        return "high"
    return None


def _step_to_dict(step) -> dict:
    # 未识别的步骤类型需按原始载荷回传，序列化结果只有 UNKNOWN 占位。
    if getattr(step, "is_unknown", False):
        return dict(step.raw)
    return step.model_dump(exclude_none=True) if hasattr(step, "model_dump") else dict(step)


class GeminiInteractionsEndpoint:
    def __init__(self, api_url: str, api_key: str, model_name: str, generation: dict | None = None):
        self.model_name = model_name.removeprefix("models/")
        self.tools = _gemini_tools()
        self.generation = generation or {}
        self.client = base.create_gemini_client(api_url, api_key)

    def _generation_config(self, tool_choice: str) -> dict:
        config = {
            "max_output_tokens": base.max_tokens,
            "tool_choice": tool_choice,
        }
        temperature_value = base._resolve_temperature(self.generation)
        if temperature_value is not None:
            config["temperature"] = temperature_value
        top_p_value = base._resolve_top_p(self.generation)
        if top_p_value is not None:
            config["top_p"] = top_p_value
        thinking_level = _gemini_thinking_level(base._resolve_reasoning_effort(self.generation))
        if thinking_level is not None:
            config["thinking_level"] = thinking_level
        return config

    async def _call(self, system_instruction: str, steps: list[dict], tool_choice: str):
        return await self.client.aio.interactions.create(
            model=self.model_name,
            input=steps,
            store=False,
            system_instruction=system_instruction or None,
            tools=self.tools,
            generation_config=self._generation_config(tool_choice),
        )

    async def create(self, messages: list[dict], tool_choice: str) -> base.ParsedResult:
        system_instruction, steps, has_signatures = _messages_to_interactions(messages, self.model_name)
        try:
            interaction = await self._call(system_instruction, steps, tool_choice)
        except Exception as exc:
            if not has_signatures or not base._is_signature_error(exc):
                raise base.gemini_error(exc, base.GeminiInteractionError, base.GeminiInteractionRateLimitError) from exc
            # 服务端判定签名失效时，改用不含 thought 步骤的上下文重试一次。
            system_instruction, steps, _ = _messages_to_interactions(messages, self.model_name, replay_signatures=False)
            try:
                interaction = await self._call(system_instruction, steps, tool_choice)
            except Exception as retry_exc:
                raise base.gemini_error(
                    retry_exc, base.GeminiInteractionError, base.GeminiInteractionRateLimitError
                ) from retry_exc
        return self._parse(interaction)

    def _parse(self, interaction) -> base.ParsedResult:
        if interaction.status == "failed":
            raise base.GeminiInteractionError(f"Interaction failed: {interaction.errors or interaction.status}")

        usage = interaction.usage
        total_input_tokens = int(usage.total_input_tokens or 0) if usage else 0
        cache_read_tokens = int(usage.total_cached_tokens or 0) if usage else 0
        total_output_tokens = int(usage.total_output_tokens or 0) if usage else 0
        total_thought_tokens = int(usage.total_thought_tokens or 0) if usage else 0
        input_tokens = max(0, total_input_tokens - cache_read_tokens)

        text_parts = []
        tool_calls = []
        raw_tool_calls = []
        model_steps = []
        for step in interaction.steps or []:
            data = _step_to_dict(step)
            step_type = data.get("type")
            if step_type in ("user_input", "function_result"):
                continue
            model_steps.append(data)
            if step_type == "model_output":
                content = data.get("content")
                if isinstance(content, str):
                    text_parts.append(content)
                    continue
                for part in content or []:
                    if isinstance(part, dict) and part.get("type") == "text":
                        text_parts.append(part.get("text", ""))
            elif step_type == "function_call":
                arguments = data.get("arguments") or {}
                if isinstance(arguments, str):
                    try:
                        arguments = orjson.loads(arguments)
                    except ValueError:
                        arguments = {}
                call_id = data.get("id", "")
                name = data.get("name", "")
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
            assistant_message["_gemini_model"] = self.model_name

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
