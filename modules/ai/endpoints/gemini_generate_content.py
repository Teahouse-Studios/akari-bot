from __future__ import annotations

import re
import uuid

import httpx
import orjson

from modules.ai.tools import TOOLS
from . import base


def _generate_content_tools() -> list[dict]:
    declarations = []
    for tool in TOOLS:
        fn = tool["function"]
        declarations.append(
            {
                "name": fn["name"],
                "description": fn["description"],
                "parameters": fn["parameters"],
            }
        )
    return [{"functionDeclarations": declarations}] if declarations else []


def _data_url_to_inline_data(data_url: str) -> dict:
    header, _, b64 = data_url.partition(",")
    mime_type = header.removeprefix("data:").split(";", maxsplit=1)[0]
    return {"inlineData": {"mimeType": mime_type, "data": b64}}


def _content_to_generate_content_parts(content: str | list | None) -> list[dict]:
    if isinstance(content, str):
        return [{"text": content}]
    if not content:
        return []
    parts = []
    for part in content:
        if not isinstance(part, dict):
            continue
        if part.get("type") == "text":
            parts.append({"text": part.get("text", "")})
        elif part.get("type") == "image_url":
            url = (part.get("image_url") or {}).get("url")
            if not url:
                continue
            if url.startswith("data:"):
                parts.append(_data_url_to_inline_data(url))
            else:
                parts.append({"fileData": {"fileUri": url}})
    return parts


def _messages_to_generate_content(messages: list[dict]) -> tuple[str, list[dict]]:
    system: list[str] = []
    contents: list[dict] = []
    tool_calls_info: dict[str, dict] = {}
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
            if contents and contents[-1]["role"] == "user":
                contents[-1]["parts"].extend(parts)
            else:
                contents.append({"role": "user", "parts": parts})
        elif role == "assistant":
            raw_parts = msg.get("_gemini_parts")
            if raw_parts:
                # 模型产生的 thoughtSignature 与函数调用步骤需原样回传。
                contents.append({"role": "model", "parts": raw_parts})
                api_ids = msg.get("_gemini_call_api_ids") or {}
                for tc in msg.get("tool_calls") or []:
                    tool_calls_info[tc["id"]] = {
                        "name": (tc.get("function") or {}).get("name", ""),
                        "api_id": api_ids.get(tc["id"]),
                    }
                continue
            parts = []
            if content:
                parts.extend(_content_to_generate_content_parts(content))
            for tc in msg.get("tool_calls") or []:
                fn = tc.get("function") or {}
                arguments = fn.get("arguments") or "{}"
                try:
                    parsed_arguments = orjson.loads(arguments)
                except ValueError:
                    parsed_arguments = {}
                parts.append({"functionCall": {"name": fn.get("name", ""), "args": parsed_arguments}})
                tool_calls_info[tc.get("id", "")] = {"name": fn.get("name", ""), "api_id": None}
            if parts:
                contents.append({"role": "model", "parts": parts})
        elif role == "tool":
            call_id = msg.get("tool_call_id", "")
            info = tool_calls_info.get(call_id, {})
            function_response = {
                "name": info.get("name") or msg.get("name") or "",
                "response": {"result": base._content_to_text(content)},
            }
            if info.get("api_id"):
                function_response["id"] = info["api_id"]
            part = {"functionResponse": function_response}
            if (
                contents
                and contents[-1]["role"] == "user"
                and any("functionResponse" in p for p in contents[-1]["parts"])
            ):
                contents[-1]["parts"].append(part)
            else:
                contents.append({"role": "user", "parts": [part]})
    return "\n\n".join(system), contents


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


def _thinking_config(effort: str | None, model_name: str) -> dict | None:
    if not effort or not _supports_thinking(model_name):
        return None
    effort = effort.lower()
    supports_level = _supports_thinking_level(model_name)
    if effort == "none":
        # Gemini 3 与 2.5 Pro 无法关闭思考，省略配置以使用模型默认行为。
        if supports_level or "pro" in model_name.lower():
            return None
        return {"thinkingBudget": 0}
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
        return {"thinkingLevel": level}
    budgets = {"MINIMAL": 1024, "LOW": 1024, "MEDIUM": 8192, "HIGH": 24576}
    return {"thinkingBudget": budgets[level]}


def _tool_config(tool_choice: str) -> dict:
    modes = {"auto": "AUTO", "none": "NONE", "any": "ANY", "validated": "VALIDATED"}
    return {"functionCallingConfig": {"mode": modes.get(tool_choice.lower(), "AUTO")}}


def _generate_content_error_message(response: httpx.Response) -> str:
    return f"{response.status_code}: {response.text[:500]}"


class GeminiGenerateContentEndpoint:
    def __init__(self, api_url: str, api_key: str, model_name: str, generation: dict | None = None):
        self.model_name = model_name
        self.tools = _generate_content_tools()
        self.generation = generation or {}
        model = model_name.removeprefix("models/")
        self.url = f"{api_url.rstrip('/')}/models/{model}:generateContent"
        self.client = httpx.AsyncClient(
            timeout=base.timeout,
            headers={"x-goog-api-key": api_key},
            follow_redirects=True,
        )

    async def create(self, messages: list[dict], tool_choice: str) -> base.ParsedResult:
        system_instruction, contents = _messages_to_generate_content(messages)
        generation_config = {
            "maxOutputTokens": base.max_tokens,
            "frequencyPenalty": base.frequency_penalty,
            "presencePenalty": base.presence_penalty,
        }
        temperature_value = base._resolve_temperature(self.generation)
        if temperature_value is not None:
            generation_config["temperature"] = temperature_value
        top_p_value = base._resolve_top_p(self.generation)
        if top_p_value is not None:
            generation_config["topP"] = top_p_value
        top_logprobs_value = base._resolve_top_logprobs(self.generation)
        if top_logprobs_value:
            generation_config["responseLogprobs"] = True
            generation_config["logprobs"] = top_logprobs_value
        thinking_config = _thinking_config(base._resolve_reasoning_effort(self.generation), self.model_name)
        if thinking_config is not None:
            generation_config["thinkingConfig"] = thinking_config

        payload = {
            "contents": contents,
            "tools": self.tools,
            "toolConfig": _tool_config(tool_choice),
            "generationConfig": generation_config,
        }
        if system_instruction:
            payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

        response = await self.client.post(self.url, json=payload)
        if response.status_code == 429:
            raise base.GeminiGenerateContentRateLimitError(_generate_content_error_message(response))
        if response.status_code >= 400:
            raise base.GeminiGenerateContentError(_generate_content_error_message(response))

        data = response.json()
        candidates = data.get("candidates") or []
        if not candidates:
            feedback = data.get("promptFeedback") or {}
            reason = feedback.get("blockReason") or feedback.get("blockReasonMessage") or "No candidates returned"
            raise base.GeminiGenerateContentError(str(reason))
        candidate = candidates[0]
        parts = (candidate.get("content") or {}).get("parts") or []

        usage = data.get("usageMetadata") or {}
        prompt_tokens = int(usage.get("promptTokenCount") or 0)
        cache_read_tokens = int(usage.get("cachedContentTokenCount") or 0)
        input_tokens = max(0, prompt_tokens - cache_read_tokens)
        # 思考 token 单独计入用量，按输出计费。
        output_tokens = int(usage.get("candidatesTokenCount") or 0) + int(usage.get("thoughtsTokenCount") or 0)

        text_parts = []
        tool_calls = []
        raw_tool_calls = []
        model_parts = []
        call_api_ids = {}
        for part in parts:
            if not isinstance(part, dict):
                continue
            model_parts.append(part)
            if part.get("thought"):
                continue
            text = part.get("text")
            if isinstance(text, str):
                text_parts.append(text)
            function_call = part.get("functionCall")
            if isinstance(function_call, dict):
                api_id = function_call.get("id")
                call_id = api_id or f"call_{uuid.uuid4().hex[:8]}"
                name = function_call.get("name", "")
                arguments = function_call.get("args") or {}
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
            assistant_message["_gemini_parts"] = model_parts
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
