from __future__ import annotations

import base64
import re
import uuid

import orjson
from google.genai import types

from modules.ai.tools import TOOLS
from . import base


def _generate_content_tools() -> list[types.Tool]:
    declarations = [
        types.FunctionDeclaration(
            name=tool["function"]["name"],
            description=tool["function"]["description"],
            parameters=tool["function"]["parameters"],
        )
        for tool in TOOLS
    ]
    return [types.Tool(function_declarations=declarations)] if declarations else []


def _data_url_to_part(data_url: str) -> types.Part:
    header, _, data = data_url.partition(",")
    mime_type = header.removeprefix("data:").split(";", maxsplit=1)[0]
    return types.Part.from_bytes(data=base64.b64decode(data), mime_type=mime_type)


def _content_to_generate_content_parts(content: str | list | None) -> list[types.Part]:
    if isinstance(content, str):
        return [types.Part(text=content)]
    if not content:
        return []
    parts = []
    for part in content:
        if not isinstance(part, dict):
            continue
        if part.get("type") == "text":
            parts.append(types.Part(text=part.get("text", "")))
        elif part.get("type") == "image_url":
            url = (part.get("image_url") or {}).get("url")
            if not url:
                continue
            if url.startswith("data:"):
                parts.append(_data_url_to_part(url))
            else:
                parts.append(types.Part(file_data=types.FileData(file_uri=url)))
    return parts


def _replay_parts(message: dict, model_name: str) -> list[types.Part] | None:
    raw_parts = message.get("_gemini_parts")
    if not raw_parts:
        return None
    produced_by = message.get("_gemini_model")
    # 签名由生成它的模型签发，跨模型回放会被判为无效签名。
    if produced_by and produced_by != model_name:
        return None
    return [types.Part.model_validate(part) for part in raw_parts]


def _messages_to_generate_content(
    messages: list[dict], model_name: str, replay_parts: bool = True
) -> tuple[str, list[types.Content], bool]:
    system: list[str] = []
    contents: list[types.Content] = []
    tool_calls_info: dict[str, dict] = {}
    dropped_calls: set[str] = set()
    has_signatures = False
    for msg in messages:
        role = msg.get("role")
        content = msg.get("content")
        if role == "system":
            system.append(base._content_to_text(content))
        elif role == "user":
            parts = _content_to_generate_content_parts(content)
            if not parts:
                continue
            # generateContent 要求 user/model 交替，工具结果后的图片消息需并入同一轮。
            if contents and contents[-1].role == "user":
                contents[-1].parts.extend(parts)
            else:
                contents.append(types.Content(role="user", parts=parts))
        elif role == "assistant":
            parts = _replay_parts(msg, model_name) if replay_parts else None
            if parts:
                has_signatures = has_signatures or any(part.thought_signature for part in parts)
                # 模型产生的 thoughtSignature 与函数调用步骤需原样回传。
                contents.append(types.Content(role="model", parts=parts))
                api_ids = msg.get("_gemini_call_api_ids") or {}
                for tc in msg.get("tool_calls") or []:
                    tool_calls_info[tc["id"]] = {
                        "name": (tc.get("function") or {}).get("name", ""),
                        "api_id": api_ids.get(tc["id"]),
                    }
                continue
            parts = _content_to_generate_content_parts(content) if content else []
            for tc in msg.get("tool_calls") or []:
                # 没有可回传的签名时无法续接函数调用，连同其结果一并舍弃。
                dropped_calls.add(tc.get("id", ""))
            if parts:
                contents.append(types.Content(role="model", parts=parts))
        elif role == "tool":
            call_id = msg.get("tool_call_id", "")
            if call_id in dropped_calls:
                continue
            info = tool_calls_info.get(call_id, {})
            function_response = types.FunctionResponse(
                name=info.get("name") or msg.get("name") or "",
                response={"result": base._content_to_text(content)},
            )
            if info.get("api_id"):
                function_response.id = info["api_id"]
            part = types.Part(function_response=function_response)
            if contents and contents[-1].role == "user" and any(p.function_response for p in contents[-1].parts):
                contents[-1].parts.append(part)
            else:
                contents.append(types.Content(role="user", parts=[part]))
    return "\n\n".join(system), contents, has_signatures


def _supports_thinking(model_name: str) -> bool:
    name = model_name.lower()
    match = re.search(r"gemini-(\d+)(?:\.(\d+))?", name)
    if match:
        major = int(match.group(1))
        minor = int(match.group(2) or 0)
        return major > 2 or (major == 2 and minor >= 5)
    return "latest" in name


def _supports_thinking_level(model_name: str) -> bool:
    name = model_name.lower()
    match = re.search(r"gemini-(\d+)", name)
    if match:
        return int(match.group(1)) >= 3
    return "latest" in name


def _thinking_config(effort: str | None, model_name: str) -> types.ThinkingConfig | None:
    if not effort or not _supports_thinking(model_name):
        return None
    effort = effort.lower()
    supports_level = _supports_thinking_level(model_name)
    if effort == "none":
        # Gemini 3 与 2.5 Pro 无法关闭思考，省略配置以使用模型默认行为。
        if supports_level or "pro" in model_name.lower():
            return None
        return types.ThinkingConfig(thinking_budget=0)
    levels = {
        "minimal": "MINIMAL",
        "low": "LOW",
        "medium": "MEDIUM",
        "high": "HIGH",
        "xhigh": "HIGH",
        "max": "HIGH",
    }
    level = levels.get(effort)
    if level is None:
        return None
    if supports_level:
        return types.ThinkingConfig(thinking_level=level)
    budgets = {"MINIMAL": 1024, "LOW": 1024, "MEDIUM": 8192, "HIGH": 24576}
    return types.ThinkingConfig(thinking_budget=budgets[level])


def _tool_config(tool_choice: str) -> types.ToolConfig:
    modes = {"auto": "AUTO", "none": "NONE", "any": "ANY", "validated": "VALIDATED"}
    return types.ToolConfig(
        function_calling_config=types.FunctionCallingConfig(mode=modes.get(tool_choice.lower(), "AUTO"))
    )


class GeminiGenerateContentEndpoint:
    def __init__(self, api_url: str, api_key: str, model_name: str, generation: dict | None = None):
        self.model_name = model_name.removeprefix("models/")
        self.tools = _generate_content_tools()
        self.generation = generation or {}
        self.client = base.create_gemini_client(api_url, api_key)

    def _config(self, system_instruction: str, tool_choice: str) -> types.GenerateContentConfig:
        config = types.GenerateContentConfig(
            system_instruction=system_instruction or None,
            max_output_tokens=base.max_tokens,
            frequency_penalty=base.frequency_penalty,
            presence_penalty=base.presence_penalty,
            tools=self.tools,
            tool_config=_tool_config(tool_choice),
        )
        temperature_value = base._resolve_temperature(self.generation)
        if temperature_value is not None:
            config.temperature = temperature_value
        top_p_value = base._resolve_top_p(self.generation)
        if top_p_value is not None:
            config.top_p = top_p_value
        top_logprobs_value = base._resolve_top_logprobs(self.generation)
        if top_logprobs_value:
            config.response_logprobs = True
            config.logprobs = top_logprobs_value
        thinking_config = _thinking_config(base._resolve_reasoning_effort(self.generation), self.model_name)
        if thinking_config is not None:
            config.thinking_config = thinking_config
        return config

    async def _call(
        self, system_instruction: str, contents: list[types.Content], tool_choice: str
    ) -> types.GenerateContentResponse:
        return await self.client.aio.models.generate_content(
            model=self.model_name,
            contents=contents,
            config=self._config(system_instruction, tool_choice),
        )

    async def create(self, messages: list[dict], tool_choice: str) -> base.ParsedResult:
        system_instruction, contents, has_signatures = _messages_to_generate_content(messages, self.model_name)
        try:
            response = await self._call(system_instruction, contents, tool_choice)
        except Exception as exc:
            if not has_signatures or not base._is_signature_error(exc):
                raise base.gemini_error(
                    exc, base.GeminiGenerateContentError, base.GeminiGenerateContentRateLimitError
                ) from exc
            # 服务端判定签名失效时，改用不含签名与工具轮次的上下文重试一次。
            system_instruction, contents, _ = _messages_to_generate_content(
                messages, self.model_name, replay_parts=False
            )
            try:
                response = await self._call(system_instruction, contents, tool_choice)
            except Exception as retry_exc:
                raise base.gemini_error(
                    retry_exc, base.GeminiGenerateContentError, base.GeminiGenerateContentRateLimitError
                ) from retry_exc
        return self._parse(response)

    def _parse(self, response: types.GenerateContentResponse) -> base.ParsedResult:
        candidates = response.candidates or []
        if not candidates:
            feedback = response.prompt_feedback
            reason = (feedback.block_reason_message or feedback.block_reason) if feedback else None
            raise base.GeminiGenerateContentError(str(reason or "No candidates returned"))
        candidate = candidates[0]
        parts = (candidate.content.parts if candidate.content else None) or []

        usage = response.usage_metadata
        prompt_tokens = int(usage.prompt_token_count or 0) if usage else 0
        cache_read_tokens = int(usage.cached_content_token_count or 0) if usage else 0
        input_tokens = max(0, prompt_tokens - cache_read_tokens)
        # 思考 token 单独计入用量，按输出计费。
        output_tokens = int(usage.candidates_token_count or 0) + int(usage.thoughts_token_count or 0) if usage else 0

        text_parts = []
        tool_calls = []
        raw_tool_calls = []
        model_parts = []
        call_api_ids = {}
        for part in parts:
            model_parts.append(part)
            if part.thought:
                continue
            if isinstance(part.text, str):
                text_parts.append(part.text)
            if part.function_call:
                api_id = part.function_call.id
                call_id = api_id or f"call_{uuid.uuid4().hex[:8]}"
                name = part.function_call.name or ""
                arguments = part.function_call.args or {}
                call_api_ids[call_id] = api_id
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
        if model_parts:
            assistant_message["_gemini_parts"] = [
                part.model_dump(mode="json", exclude_none=True) for part in model_parts
            ]
            assistant_message["_gemini_model"] = self.model_name
        if call_api_ids:
            assistant_message["_gemini_call_api_ids"] = call_api_ids

        return base.ParsedResult(
            text=text,
            tool_calls=tool_calls,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read_tokens,
            cache_write_tokens=0,
            assistant_message=assistant_message,
        )
