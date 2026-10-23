"""modules.ai Gemini GenerateContent API 端点单元测试。"""

from types import SimpleNamespace

from google.genai import errors, types

from core.tester import func_case, Tester
from modules.ai import endpoints


class _FakeAPIError(Exception):
    def __init__(self, code: int, message: str = "api error"):
        super().__init__(message)
        self.code = code


class _FakeModels:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def generate_content(self, *, model, contents, config):
        self.calls.append({"model": model, "contents": contents, "config": config})
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _build_endpoint(model_name="gemini-3.5-flash", generation=None, *responses):
    endpoint = endpoints.GeminiGenerateContentEndpoint(
        "https://generativelanguage.googleapis.com/v1beta",
        "key",
        model_name,
        generation,
    )
    models = _FakeModels(responses)
    endpoint.client = SimpleNamespace(aio=SimpleNamespace(models=models))
    return endpoint, models


def _response(parts, usage=None, **kwargs):
    payload = {"candidates": [{"content": {"role": "model", "parts": parts}}]}
    if usage:
        payload["usageMetadata"] = usage
    payload.update(kwargs)
    return types.GenerateContentResponse.model_validate(payload)


def _dump(content: types.Content) -> dict:
    return content.model_dump(exclude_none=True)


def _dump_parts(parts) -> list[dict]:
    return [part.model_dump(mode="json", exclude_none=True) for part in parts]


def _test_build_endpoint():
    endpoint = endpoints.build_endpoint(
        "gemini",
        "https://generativelanguage.googleapis.com/v1beta",
        "key",
        "models/gemini-3.5-flash",
    )
    assert isinstance(endpoint, endpoints.GeminiGenerateContentEndpoint)
    assert endpoint.model_name == "gemini-3.5-flash"
    assert endpoints._split_api_url("https://cf.api.fan/v1beta") == ("https://cf.api.fan", "v1beta")
    assert endpoints._split_api_url("https://generativelanguage.googleapis.com") == (
        "https://generativelanguage.googleapis.com",
        "v1beta",
    )
    return True


def _test_messages_are_converted_to_contents():
    messages = [
        {"role": "system", "content": "sys1"},
        {"role": "system", "content": "sys2"},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "hi"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}},
            ],
        },
        {
            "role": "assistant",
            "content": "answer",
            "tool_calls": [
                {"id": "call_1", "type": "function", "function": {"name": "search_web", "arguments": '{"query": "x"}'}}
            ],
        },
        {"role": "tool", "tool_call_id": "call_1", "content": "result"},
    ]
    system, contents, has_signatures = endpoints._messages_to_generate_content(messages, "gemini-3.5-flash")
    assert system == "sys1\n\nsys2"
    assert not has_signatures
    assert [_dump(content) for content in contents] == [
        {
            "role": "user",
            "parts": [
                {"text": "hi"},
                {"inline_data": {"data": b"\x00\x00\x00", "mime_type": "image/png"}},
            ],
        },
        {"role": "model", "parts": [{"text": "answer"}]},
    ]
    return True


def _test_raw_parts_are_replayed():
    stored_parts = [
        {"text": "thinking", "thought": True, "thought_signature": "c2lnMQ=="},
        {
            "function_call": {"id": "fc_1", "name": "search_web", "args": {"query": "x"}},
            "thought_signature": "c2lnMg==",
        },
    ]
    messages = [
        {
            "role": "assistant",
            "content": "ignored",
            "tool_calls": [{"id": "fc_1", "type": "function", "function": {"name": "search_web", "arguments": "{}"}}],
            "_gemini_parts": stored_parts,
            "_gemini_call_api_ids": {"fc_1": "fc_1"},
            "_gemini_model": "gemini-3.5-flash",
        },
        {"role": "tool", "tool_call_id": "fc_1", "content": "result"},
    ]
    _, contents, has_signatures = endpoints._messages_to_generate_content(messages, "gemini-3.5-flash")
    assert has_signatures
    assert _dump_parts(contents[0].parts) == stored_parts
    assert _dump(contents[1]) == {
        "role": "user",
        "parts": [{"function_response": {"id": "fc_1", "name": "search_web", "response": {"result": "result"}}}],
    }
    return True


def _test_signatures_are_dropped_across_models():
    messages = [
        {
            "role": "assistant",
            "content": "answer",
            "tool_calls": [{"id": "fc_1", "type": "function", "function": {"name": "search_web", "arguments": "{}"}}],
            "_gemini_parts": [
                {"function_call": {"id": "fc_1", "name": "search_web", "args": {}}, "thought_signature": "c2ln"}
            ],
            "_gemini_model": "gemini-3.5-flash",
        },
        {"role": "tool", "tool_call_id": "fc_1", "content": "result"},
    ]
    _, contents, has_signatures = endpoints._messages_to_generate_content(messages, "gemini-3.1-pro-preview")
    assert not has_signatures
    assert [_dump(content) for content in contents] == [{"role": "model", "parts": [{"text": "answer"}]}]
    return True


def _test_parallel_tool_results_are_merged():
    messages = [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"id": "call_1", "type": "function", "function": {"name": "search_web", "arguments": "{}"}},
                {"id": "call_2", "type": "function", "function": {"name": "fetch_webpage", "arguments": "{}"}},
            ],
            "_gemini_parts": [
                {"function_call": {"id": "fc_1", "name": "search_web", "args": {}}, "thought_signature": "c2lnMQ=="},
                {"function_call": {"id": "fc_2", "name": "fetch_webpage", "args": {}}, "thought_signature": "c2lnMg=="},
            ],
            "_gemini_call_api_ids": {"call_1": "fc_1", "call_2": "fc_2"},
            "_gemini_model": "gemini-3.5-flash",
        },
        {"role": "tool", "tool_call_id": "call_1", "content": "first"},
        {"role": "tool", "tool_call_id": "call_2", "content": "second"},
    ]
    _, contents, _ = endpoints._messages_to_generate_content(messages, "gemini-3.5-flash")
    assert _dump(contents[-1]) == {
        "role": "user",
        "parts": [
            {"function_response": {"id": "fc_1", "name": "search_web", "response": {"result": "first"}}},
            {"function_response": {"id": "fc_2", "name": "fetch_webpage", "response": {"result": "second"}}},
        ],
    }
    return True


def _test_tool_image_message_is_merged():
    messages = [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"id": "call_1", "type": "function", "function": {"name": "generate_image", "arguments": "{}"}}
            ],
            "_gemini_parts": [
                {
                    "function_call": {"id": "fc_1", "name": "generate_image", "args": {}},
                    "thought_signature": "c2ln",
                }
            ],
            "_gemini_call_api_ids": {"call_1": "fc_1"},
            "_gemini_model": "gemini-3.5-flash",
        },
        {"role": "tool", "tool_call_id": "call_1", "content": "done"},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "images"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}},
            ],
        },
    ]
    _, contents, _ = endpoints._messages_to_generate_content(messages, "gemini-3.5-flash")
    assert _dump(contents[-1]) == {
        "role": "user",
        "parts": [
            {"function_response": {"id": "fc_1", "name": "generate_image", "response": {"result": "done"}}},
            {"text": "images"},
            {"inline_data": {"data": b"\x00\x00\x00", "mime_type": "image/png"}},
        ],
    }
    return True


def _test_thinking_config():
    assert endpoints._supports_thinking_level("gemini-3.5-flash")
    assert endpoints._supports_thinking_level("gemini-4-argon")
    assert endpoints._supports_thinking_level("gemini-flash-latest")
    assert not endpoints._supports_thinking_level("gemini-2.5-flash")
    config = endpoints._thinking_config("high", "gemini-3.5-flash")
    assert config.model_dump(exclude_none=True) == {"thinking_level": "HIGH"}
    assert endpoints._thinking_config("none", "gemini-3.5-flash") is None
    assert endpoints._thinking_config("none", "gemini-2.5-pro") is None
    assert endpoints._thinking_config("none", "gemini-2.5-flash").model_dump(exclude_none=True) == {
        "thinking_budget": 0
    }
    assert endpoints._thinking_config("medium", "gemini-2.5-flash").model_dump(exclude_none=True) == {
        "thinking_budget": 8192
    }
    assert endpoints._thinking_config("high", "gemini-2.0-flash") is None
    return True


async def _test_request_payload():
    endpoint, models = _build_endpoint(
        "gemini-3.5-flash",
        {"temperature": 0.2, "top_p": 0.9, "top_logprobs": 5, "reasoning_effort": "high"},
        _response([{"text": "ok"}]),
    )
    await endpoint.create(
        [{"role": "system", "content": "sys"}, {"role": "user", "content": "hi"}],
        "auto",
    )
    call = models.calls[0]
    assert call["model"] == "gemini-3.5-flash"
    assert _dump(call["contents"][0]) == {"role": "user", "parts": [{"text": "hi"}]}
    config = call["config"].model_dump(exclude_none=True)
    assert config["system_instruction"] == "sys"
    assert config["max_output_tokens"] == endpoints.base.max_tokens
    assert config["frequency_penalty"] == endpoints.base.frequency_penalty
    assert config["presence_penalty"] == endpoints.base.presence_penalty
    assert config["temperature"] == 0.2
    assert config["top_p"] == 0.9
    assert config["response_logprobs"] is True
    assert config["logprobs"] == 5
    assert config["tool_config"] == {"function_calling_config": {"mode": "AUTO"}}
    assert config["thinking_config"] == {"thinking_level": "HIGH"}
    declaration = config["tools"][0]["function_declarations"][0]
    assert declaration["name"]
    assert "parameters" in declaration
    return True


async def _test_request_omits_defaults():
    endpoint, models = _build_endpoint(
        "gemini-2.5-flash",
        {"temperature": 1, "top_p": 1, "top_logprobs": -1, "reasoning_effort": "none"},
        _response([{"text": "ok"}]),
    )
    await endpoint.create([{"role": "user", "content": "hi"}], "none")
    config = models.calls[0]["config"].model_dump(exclude_none=True)
    assert config["tool_config"] == {"function_calling_config": {"mode": "NONE"}}
    assert "temperature" not in config
    assert "top_p" not in config
    assert "response_logprobs" not in config
    assert "logprobs" not in config
    assert config["thinking_config"] == {"thinking_budget": 0}
    return True


async def _test_response_is_parsed():
    parts = [
        {"text": "thinking", "thought": True, "thoughtSignature": "c2lnMQ=="},
        {"text": "hello "},
        {"text": "world"},
        {
            "functionCall": {"id": "fc_1", "name": "search_web", "args": {"query": "x"}},
            "thoughtSignature": "c2lnMg==",
        },
    ]
    response = _response(
        parts,
        usage={
            "promptTokenCount": 100,
            "cachedContentTokenCount": 40,
            "candidatesTokenCount": 10,
            "thoughtsTokenCount": 5,
        },
    )
    endpoint, _ = _build_endpoint("gemini-3.5-flash", None, response)
    result = await endpoint.create([{"role": "user", "content": "hi"}], "auto")
    assert result.text == "hello world"
    assert result.input_tokens == 60
    assert result.cache_read_tokens == 40
    assert result.cache_write_tokens == 0
    assert result.output_tokens == 15
    assert [call.id for call in result.tool_calls] == ["fc_1"]
    assert result.tool_calls[0].name == "search_web"
    assert result.tool_calls[0].arguments == {"query": "x"}
    assert result.assistant_message["content"] == "hello world"
    assert result.assistant_message["tool_calls"] == [
        {
            "id": "fc_1",
            "type": "function",
            "function": {"name": "search_web", "arguments": '{"query":"x"}'},
        }
    ]
    assert result.assistant_message["_gemini_parts"] == _dump_parts(response.candidates[0].content.parts)
    assert result.assistant_message["_gemini_model"] == "gemini-3.5-flash"
    assert result.assistant_message["_gemini_call_api_ids"] == {"fc_1": "fc_1"}
    return True


async def _test_response_without_function_call_id():
    response = _response([{"functionCall": {"name": "search_web", "args": {}}}])
    endpoint, _ = _build_endpoint("gemini-2.5-flash", None, response)
    result = await endpoint.create([{"role": "user", "content": "hi"}], "auto")
    call_id = result.tool_calls[0].id
    assert call_id.startswith("call_")
    assert result.assistant_message["_gemini_call_api_ids"] == {call_id: None}
    _, contents, _ = endpoints._messages_to_generate_content(
        [
            result.assistant_message,
            {"role": "tool", "tool_call_id": call_id, "content": "result"},
        ],
        "gemini-2.5-flash",
    )
    assert "id" not in _dump(contents[-1])["parts"][0]["function_response"]
    return True


async def _test_invalid_signature_is_retried():
    signed_message = {
        "role": "assistant",
        "content": "answer",
        "tool_calls": [{"id": "fc_1", "type": "function", "function": {"name": "search_web", "arguments": "{}"}}],
        "_gemini_parts": [
            {"function_call": {"id": "fc_1", "name": "search_web", "args": {}}, "thought_signature": "c2ln"}
        ],
        "_gemini_call_api_ids": {"fc_1": "fc_1"},
        "_gemini_model": "gemini-3.5-flash",
    }
    messages = [signed_message, {"role": "tool", "tool_call_id": "fc_1", "content": "result"}]
    endpoint, models = _build_endpoint(
        "gemini-3.5-flash",
        None,
        _FakeAPIError(400, "Thought signature is invalid."),
        _response([{"text": "ok"}]),
    )
    result = await endpoint.create(messages, "auto")
    assert result.text == "ok"
    assert len(models.calls) == 2
    assert any(part.thought_signature for content in models.calls[0]["contents"] for part in content.parts)
    assert not any(part.thought_signature for content in models.calls[1]["contents"] for part in content.parts)
    return True


async def _test_invalid_signature_without_history_is_fatal():
    endpoint, models = _build_endpoint("gemini-3.5-flash", None, _FakeAPIError(400, "Thought signature is invalid."))
    try:
        await endpoint.create([{"role": "user", "content": "hi"}], "auto")
    except endpoints.GeminiGenerateContentError as exc:
        assert "Thought signature" in str(exc)
    else:
        raise AssertionError("expected api error")
    assert len(models.calls) == 1
    return True


async def _test_rate_limit_is_retryable():
    endpoint, _ = _build_endpoint("gemini-3.5-flash", None, _FakeAPIError(429, "rate limited"))
    try:
        await endpoint.create([{"role": "user", "content": "hi"}], "auto")
    except endpoints.GeminiGenerateContentRateLimitError as exc:
        assert "rate limited" in str(exc)
    else:
        raise AssertionError("expected rate limit error")
    assert endpoints.GeminiGenerateContentRateLimitError in endpoints.RETRYABLE_EXCEPTIONS
    return True


async def _test_api_error_is_raised():
    endpoint, _ = _build_endpoint("gemini-3.5-flash", None, _FakeAPIError(400, "bad request"))
    try:
        await endpoint.create([{"role": "user", "content": "hi"}], "auto")
    except endpoints.GeminiGenerateContentError as exc:
        assert "bad request" in str(exc)
    else:
        raise AssertionError("expected api error")
    return True


def _test_sdk_error_is_translated():
    exc = endpoints.gemini_error(
        errors.ClientError(400, {"error": {"message": "bad"}}),
        endpoints.GeminiGenerateContentError,
        endpoints.GeminiGenerateContentRateLimitError,
    )
    assert isinstance(exc, endpoints.GeminiGenerateContentError)
    assert (
        endpoints.gemini_error(
            _FakeAPIError(429), endpoints.GeminiGenerateContentError, endpoints.GeminiGenerateContentRateLimitError
        ).__class__
        is endpoints.GeminiGenerateContentRateLimitError
    )
    return True


async def _test_blocked_prompt_is_raised():
    response = types.GenerateContentResponse.model_validate({"promptFeedback": {"blockReason": "SAFETY"}})
    endpoint, _ = _build_endpoint("gemini-3.5-flash", None, response)
    try:
        await endpoint.create([{"role": "user", "content": "hi"}], "auto")
    except endpoints.GeminiGenerateContentError as exc:
        assert "SAFETY" in str(exc)
    else:
        raise AssertionError("expected blocked prompt error")
    return True


@func_case
async def test_ai_gemini_generate_content(tester: Tester):
    """modules.ai: Gemini GenerateContent API 端点请求与响应转换"""
    await tester.test(_test_build_endpoint, "build_endpoint 返回 GenerateContent 端点")
    await tester.test(_test_messages_are_converted_to_contents, "消息转换为 GenerateContent contents")
    await tester.test(_test_raw_parts_are_replayed, "原始模型 parts 原样回放")
    await tester.test(_test_signatures_are_dropped_across_models, "跨模型时不回放签名与工具轮次")
    await tester.test(_test_parallel_tool_results_are_merged, "并行工具结果合并为一轮")
    await tester.test(_test_tool_image_message_is_merged, "工具图片并入函数结果轮次")
    await tester.test(_test_thinking_config, "思考配置按模型代次映射")
    await tester.test(_test_request_payload, "请求载荷包含模型、工具与生成配置")
    await tester.test(_test_request_omits_defaults, "默认采样与关闭思考时省略对应字段")
    await tester.test(_test_response_is_parsed, "响应解析文本、工具调用与用量")
    await tester.test(_test_response_without_function_call_id, "缺少函数调用 ID 时生成内部 ID")
    await tester.test(_test_invalid_signature_is_retried, "签名失效时改用无签名上下文重试")
    await tester.test(_test_invalid_signature_without_history_is_fatal, "无签名历史时不重试")
    await tester.test(_test_rate_limit_is_retryable, "429 归入可重试异常")
    await tester.test(_test_api_error_is_raised, "其他 HTTP 错误抛出端点异常")
    await tester.test(_test_sdk_error_is_translated, "SDK 异常转换为端点异常")
    await tester.test(_test_blocked_prompt_is_raised, "提示被拦截时抛出端点异常")
    return tester
