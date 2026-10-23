"""modules.ai Gemini Interactions API 端点单元测试。"""

from types import SimpleNamespace

from google.genai import interactions as gemini_interactions

from core.tester import func_case, Tester
from modules.ai import endpoints


class _FakeAPIError(Exception):
    def __init__(self, code: int, message: str = "api error"):
        super().__init__(message)
        self.code = code


class _FakeInteractions:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _build_endpoint(generation=None, *responses):
    endpoint = endpoints.GeminiInteractionsEndpoint(
        "https://generativelanguage.googleapis.com/v1beta",
        "key",
        "models/gemini-3.5-flash",
        generation,
    )
    interactions = _FakeInteractions(responses)
    endpoint.client = SimpleNamespace(aio=SimpleNamespace(interactions=interactions))
    return endpoint, interactions


def _interaction(steps, usage=None, **kwargs):
    payload = {"id": "int_1", "status": "completed", "model": "gemini-3.5-flash", "steps": steps}
    if usage:
        payload["usage"] = usage
    payload.update(kwargs)
    return gemini_interactions.Interaction.model_validate(payload)


def _test_build_endpoint():
    endpoint = endpoints.build_endpoint(
        "gemini-interaction",
        "https://generativelanguage.googleapis.com/v1beta",
        "key",
        "gemini-3.5-flash",
    )
    assert isinstance(endpoint, endpoints.GeminiInteractionsEndpoint)
    assert endpoint.model_name == "gemini-3.5-flash"
    return True


def _test_messages_are_converted_to_steps():
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
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "search_web", "arguments": '{"query": "x"}'},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "call_1", "content": "result"},
    ]
    system, steps, has_signatures = endpoints._messages_to_interactions(messages, "gemini-3.5-flash")
    assert system == "sys1\n\nsys2"
    assert not has_signatures
    assert steps == [
        {
            "type": "user_input",
            "content": [
                {"type": "text", "text": "hi"},
                {"type": "image", "mime_type": "image/png", "data": "AAAA"},
            ],
        },
        {"type": "model_output", "content": [{"type": "text", "text": "answer"}]},
        {"type": "function_call", "id": "call_1", "name": "search_web", "arguments": {"query": "x"}},
        {
            "type": "function_result",
            "call_id": "call_1",
            "name": "search_web",
            "result": [{"type": "text", "text": "result"}],
        },
    ]
    return True


def _test_remote_image_url_is_preserved():
    parts = endpoints._content_to_interactions(
        [{"type": "image_url", "image_url": {"url": "https://example.com/image.jpg"}}]
    )
    assert parts == [{"type": "image", "uri": "https://example.com/image.jpg"}]
    return True


def _test_gemini_steps_are_replayed_verbatim():
    raw_steps = [
        {"type": "thought", "signature": "c2ln"},
        {"type": "model_output", "content": [{"type": "text", "text": "hello"}]},
        {"type": "function_call", "id": "call_1", "name": "search_web", "arguments": {}},
    ]
    messages = [
        {
            "role": "assistant",
            "content": "ignored",
            "tool_calls": [{"id": "call_1", "type": "function", "function": {"name": "search_web", "arguments": "{}"}}],
            "_gemini_steps": raw_steps,
            "_gemini_model": "gemini-3.5-flash",
        },
        {"role": "tool", "tool_call_id": "call_1", "content": "result"},
    ]
    _, steps, has_signatures = endpoints._messages_to_interactions(messages, "gemini-3.5-flash")
    assert has_signatures
    assert steps[: len(raw_steps)] == raw_steps
    assert steps[-1] == {
        "type": "function_result",
        "call_id": "call_1",
        "name": "search_web",
        "result": [{"type": "text", "text": "result"}],
    }
    return True


def _test_thought_steps_are_dropped_across_models():
    messages = [
        {
            "role": "assistant",
            "content": "hello",
            "_gemini_steps": [
                {"type": "thought", "signature": "c2ln"},
                {"type": "model_output", "content": [{"type": "text", "text": "hello"}]},
            ],
            "_gemini_model": "gemini-3.5-flash",
        }
    ]
    _, steps, has_signatures = endpoints._messages_to_interactions(messages, "gemini-3.1-pro-preview")
    assert not has_signatures
    assert steps == [{"type": "model_output", "content": [{"type": "text", "text": "hello"}]}]
    return True


def _test_tool_image_message_is_merged_into_function_result():
    messages = [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"id": "call_1", "type": "function", "function": {"name": "generate_image", "arguments": "{}"}}
            ],
            "_gemini_steps": [{"type": "function_call", "id": "call_1", "name": "generate_image", "arguments": {}}],
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
    _, steps, _ = endpoints._messages_to_interactions(messages, "gemini-3.5-flash")
    assert steps[-1] == {
        "type": "function_result",
        "call_id": "call_1",
        "name": "generate_image",
        "result": [
            {"type": "text", "text": "done"},
            {"type": "text", "text": "images"},
            {"type": "image", "mime_type": "image/png", "data": "AAAA"},
        ],
    }
    return True


def _test_unknown_step_is_replayed_raw():
    step = SimpleNamespace(is_unknown=True, raw={"type": "mystery", "foo": "bar"})
    assert endpoints._step_to_dict(step) == {"type": "mystery", "foo": "bar"}
    return True


def _test_thinking_level_mapping():
    assert endpoints._gemini_thinking_level("minimal") == "minimal"
    assert endpoints._gemini_thinking_level("medium") == "medium"
    assert endpoints._gemini_thinking_level("xhigh") == "high"
    assert endpoints._gemini_thinking_level("max") == "high"
    assert endpoints._gemini_thinking_level("none") is None
    assert endpoints._gemini_thinking_level(None) is None
    return True


async def _test_request_payload():
    endpoint, interactions = _build_endpoint(
        {"temperature": 0.2, "top_p": 0.9, "reasoning_effort": "medium"},
        _interaction([{"type": "model_output", "content": [{"type": "text", "text": "ok"}]}]),
    )
    await endpoint.create([{"role": "system", "content": "sys"}, {"role": "user", "content": "hi"}], "auto")
    call = interactions.calls[0]
    assert call["model"] == "gemini-3.5-flash"
    assert call["input"] == [{"type": "user_input", "content": [{"type": "text", "text": "hi"}]}]
    assert call["store"] is False
    assert call["system_instruction"] == "sys"
    assert call["tools"][0]["type"] == "function"
    assert call["generation_config"] == {
        "max_output_tokens": endpoints.base.max_tokens,
        "tool_choice": "auto",
        "temperature": 0.2,
        "top_p": 0.9,
        "thinking_level": "medium",
    }
    return True


async def _test_request_omits_default_sampling_and_disabled_thinking():
    endpoint, interactions = _build_endpoint(
        {"temperature": 1, "top_p": 1, "reasoning_effort": "none"},
        _interaction([{"type": "model_output", "content": [{"type": "text", "text": "ok"}]}]),
    )
    await endpoint.create([{"role": "user", "content": "hi"}], "none")
    call = interactions.calls[0]
    assert call["system_instruction"] is None
    assert call["generation_config"] == {
        "max_output_tokens": endpoints.base.max_tokens,
        "tool_choice": "none",
    }
    return True


async def _test_response_is_parsed():
    thought = {"type": "thought", "signature": "c2ln", "summary": [{"type": "text", "text": "hmm"}]}
    model_output = {"type": "model_output", "content": [{"type": "text", "text": "hello "}]}
    model_output_2 = {"type": "model_output", "content": [{"type": "text", "text": "world"}]}
    function_call = {"type": "function_call", "id": "call_1", "name": "search_web", "arguments": {"query": "x"}}
    response = _interaction(
        [
            {"type": "user_input", "content": [{"type": "text", "text": "hi"}]},
            thought,
            model_output,
            model_output_2,
            function_call,
        ],
        usage={
            "total_input_tokens": 100,
            "total_cached_tokens": 40,
            "total_output_tokens": 10,
            "total_thought_tokens": 5,
        },
    )
    endpoint, _ = _build_endpoint(None, response)
    result = await endpoint.create([{"role": "user", "content": "hi"}], "auto")
    assert result.text == "hello world"
    assert result.input_tokens == 60
    assert result.cache_read_tokens == 40
    assert result.cache_write_tokens == 0
    assert result.output_tokens == 15
    assert [call.id for call in result.tool_calls] == ["call_1"]
    assert result.tool_calls[0].name == "search_web"
    assert result.tool_calls[0].arguments == {"query": "x"}
    assert result.assistant_message["content"] == "hello world"
    assert result.assistant_message["tool_calls"] == [
        {
            "id": "call_1",
            "type": "function",
            "function": {"name": "search_web", "arguments": '{"query":"x"}'},
        }
    ]
    assert result.assistant_message["_gemini_steps"] == [thought, model_output, model_output_2, function_call]
    assert result.assistant_message["_gemini_model"] == "gemini-3.5-flash"
    return True


async def _test_invalid_signature_is_retried():
    signed_message = {
        "role": "assistant",
        "content": "hello",
        "_gemini_steps": [
            {"type": "thought", "signature": "c2ln"},
            {"type": "model_output", "content": [{"type": "text", "text": "hello"}]},
        ],
        "_gemini_model": "gemini-3.5-flash",
    }
    endpoint, interactions = _build_endpoint(
        None,
        _FakeAPIError(400, "Thought signature is invalid."),
        _interaction([{"type": "model_output", "content": [{"type": "text", "text": "ok"}]}]),
    )
    result = await endpoint.create([signed_message], "auto")
    assert result.text == "ok"
    assert len(interactions.calls) == 2
    assert any(step["type"] == "thought" for step in interactions.calls[0]["input"])
    assert not any(step["type"] == "thought" for step in interactions.calls[1]["input"])
    return True


async def _test_rate_limit_is_retryable():
    endpoint, _ = _build_endpoint(None, _FakeAPIError(429, "rate limited"))
    try:
        await endpoint.create([{"role": "user", "content": "hi"}], "auto")
    except endpoints.GeminiInteractionRateLimitError as exc:
        assert "rate limited" in str(exc)
    else:
        raise AssertionError("expected rate limit error")
    assert endpoints.GeminiInteractionRateLimitError in endpoints.RETRYABLE_EXCEPTIONS
    return True


async def _test_api_error_is_raised():
    endpoint, _ = _build_endpoint(None, _FakeAPIError(400, "bad request"))
    try:
        await endpoint.create([{"role": "user", "content": "hi"}], "auto")
    except endpoints.GeminiInteractionError as exc:
        assert "bad request" in str(exc)
    else:
        raise AssertionError("expected api error")
    return True


async def _test_failed_status_is_raised():
    response = gemini_interactions.Interaction.model_validate(
        {
            "id": "int_1",
            "status": "failed",
            "model": "gemini-3.5-flash",
            "errors": [{"code": "400", "message": "bad"}],
        }
    )
    endpoint, _ = _build_endpoint(None, response)
    try:
        await endpoint.create([{"role": "user", "content": "hi"}], "auto")
    except endpoints.GeminiInteractionError as exc:
        assert "bad" in str(exc) or "failed" in str(exc)
    else:
        raise AssertionError("expected failed status error")
    return True


@func_case
async def test_ai_gemini_interactions(tester: Tester):
    """modules.ai: Gemini Interactions API 端点请求与响应转换"""
    await tester.test(_test_build_endpoint, "build_endpoint 返回 Gemini 端点")
    await tester.test(_test_messages_are_converted_to_steps, "消息转换为 Interactions 步骤")
    await tester.test(_test_remote_image_url_is_preserved, "远程图片以 uri 保留")
    await tester.test(_test_gemini_steps_are_replayed_verbatim, "原始模型步骤原样回放")
    await tester.test(_test_thought_steps_are_dropped_across_models, "跨模型时不回放 thought 步骤")
    await tester.test(_test_tool_image_message_is_merged_into_function_result, "工具图片并入函数结果")
    await tester.test(_test_unknown_step_is_replayed_raw, "未识别步骤按原始载荷回传")
    await tester.test(_test_thinking_level_mapping, "思考强度映射为 thinking_level")
    await tester.test(_test_request_payload, "请求载荷包含模型、工具与生成配置")
    await tester.test(_test_request_omits_default_sampling_and_disabled_thinking, "默认采样与关闭思考时省略对应字段")
    await tester.test(_test_response_is_parsed, "响应解析文本、工具调用与用量")
    await tester.test(_test_invalid_signature_is_retried, "签名失效时改用无 thought 步骤的上下文重试")
    await tester.test(_test_rate_limit_is_retryable, "429 归入可重试异常")
    await tester.test(_test_api_error_is_raised, "其他 HTTP 错误抛出端点异常")
    await tester.test(_test_failed_status_is_raised, "失败状态抛出端点异常")
    return tester
