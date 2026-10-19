"""modules.ai Gemini Interactions API 端点单元测试。"""

import orjson

from core.tester import func_case, Tester
from modules.ai import endpoints


class _FakeResponse:
    def __init__(self, payload=None, status_code=200, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text or orjson.dumps(self._payload).decode("utf-8")

    def json(self):
        return self._payload


class _FakeClient:
    def __init__(self, response=None):
        self.response = response or _FakeResponse()
        self.requests = []

    async def post(self, url, json=None):
        self.requests.append((url, json))
        return self.response


def _build_endpoint(generation=None, response=None):
    endpoint = endpoints.GeminiInteractionsEndpoint(
        "https://generativelanguage.googleapis.com/v1beta",
        "key",
        "gemini-3.5-flash",
        generation,
    )
    client = _FakeClient(response)
    endpoint.client = client
    return endpoint, client


def _test_build_endpoint():
    endpoint = endpoints.build_endpoint(
        "gemini-interaction",
        "https://generativelanguage.googleapis.com/v1beta",
        "key",
        "gemini-3.5-flash",
    )
    assert isinstance(endpoint, endpoints.GeminiInteractionsEndpoint)
    assert endpoint.url == "https://generativelanguage.googleapis.com/v1beta/interactions"
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
    system, steps = endpoints._messages_to_interactions(messages)
    assert system == "sys1\n\nsys2"
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
        {"type": "thought", "signature": "sig"},
        {"type": "function_call", "id": "call_1", "name": "search_web", "arguments": {"query": "x"}},
    ]
    messages = [
        {
            "role": "assistant",
            "content": "ignored",
            "tool_calls": [{"id": "call_1", "type": "function", "function": {"name": "search_web", "arguments": "{}"}}],
            "_gemini_steps": raw_steps,
        },
        {"role": "tool", "tool_call_id": "call_1", "content": "result"},
    ]
    _, steps = endpoints._messages_to_interactions(messages)
    assert steps == [
        *raw_steps,
        {
            "type": "function_result",
            "call_id": "call_1",
            "name": "search_web",
            "result": [{"type": "text", "text": "result"}],
        },
    ]
    return True


def _test_tool_image_message_is_merged_into_function_result():
    messages = [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"id": "call_1", "type": "function", "function": {"name": "generate_image", "arguments": "{}"}}
            ],
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
    _, steps = endpoints._messages_to_interactions(messages)
    assert steps == [
        {"type": "function_call", "id": "call_1", "name": "generate_image", "arguments": {}},
        {
            "type": "function_result",
            "call_id": "call_1",
            "name": "generate_image",
            "result": [
                {"type": "text", "text": "done"},
                {"type": "text", "text": "images"},
                {"type": "image", "mime_type": "image/png", "data": "AAAA"},
            ],
        },
    ]
    return True


def _test_thinking_level_mapping():
    assert endpoints._gemini_thinking_level("minimal") == "minimal"
    assert endpoints._gemini_thinking_level("low") == "low"
    assert endpoints._gemini_thinking_level("xhigh") == "high"
    assert endpoints._gemini_thinking_level("max") == "high"
    assert endpoints._gemini_thinking_level("none") is None
    assert endpoints._gemini_thinking_level(None) is None
    assert endpoints._gemini_thinking_level("unsupported") is None
    return True


async def _test_request_payload():
    endpoint, client = _build_endpoint(generation={"temperature": 0.2, "top_p": 0.9, "reasoning_effort": "xhigh"})
    await endpoint.create(
        [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": [{"type": "text", "text": "hi"}]},
        ],
        "auto",
    )
    url, payload = client.requests[0]
    assert url == "https://generativelanguage.googleapis.com/v1beta/interactions"
    assert payload["model"] == "gemini-3.5-flash"
    assert payload["store"] is False
    assert payload["system_instruction"] == "sys"
    assert payload["input"] == [{"type": "user_input", "content": [{"type": "text", "text": "hi"}]}]
    assert payload["tools"][0]["type"] == "function"
    assert payload["generation_config"] == {
        "max_output_tokens": endpoints.max_tokens,
        "tool_choice": "auto",
        "temperature": 0.2,
        "top_p": 0.9,
        "thinking_level": "high",
    }
    return True


async def _test_request_omits_default_sampling_and_disabled_thinking():
    endpoint, client = _build_endpoint(generation={"temperature": 1, "top_p": 1, "reasoning_effort": "none"})
    await endpoint.create([{"role": "user", "content": "hi"}], "none")
    _, payload = client.requests[0]
    config = payload["generation_config"]
    assert config["tool_choice"] == "none"
    assert "temperature" not in config
    assert "top_p" not in config
    assert "thinking_level" not in config
    assert "system_instruction" not in payload
    return True


async def _test_response_is_parsed():
    thought = {"type": "thought", "signature": "sig", "summary": [{"type": "text", "text": "thinking"}]}
    model_output = {
        "type": "model_output",
        "content": [{"type": "text", "text": "hello "}, {"type": "text", "text": "world"}],
    }
    function_call = {"type": "function_call", "id": "call_1", "name": "search_web", "arguments": {"query": "x"}}
    response = _FakeResponse(
        {
            "status": "requires_action",
            "usage": {
                "total_input_tokens": 100,
                "total_cached_tokens": 40,
                "total_output_tokens": 10,
                "total_thought_tokens": 5,
            },
            "steps": [
                {"type": "user_input", "content": [{"type": "text", "text": "hi"}]},
                thought,
                model_output,
                function_call,
            ],
        }
    )
    endpoint, _ = _build_endpoint(response=response)
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
    assert result.assistant_message["_gemini_steps"] == [thought, model_output, function_call]
    return True


async def _test_rate_limit_is_retryable():
    endpoint, _ = _build_endpoint(response=_FakeResponse(status_code=429, text="rate limited"))
    try:
        await endpoint.create([], "auto")
    except endpoints.GeminiInteractionRateLimitError as exc:
        assert "429" in str(exc)
    else:
        raise AssertionError("expected rate limit error")
    assert endpoints.GeminiInteractionRateLimitError in endpoints.RETRYABLE_EXCEPTIONS
    return True


async def _test_api_error_is_raised():
    endpoint, _ = _build_endpoint(response=_FakeResponse(status_code=400, text="bad request"))
    try:
        await endpoint.create([], "auto")
    except endpoints.GeminiInteractionError as exc:
        assert "400" in str(exc)
    else:
        raise AssertionError("expected api error")
    return True


async def _test_failed_status_is_raised():
    endpoint, _ = _build_endpoint(response=_FakeResponse({"status": "failed", "errors": [{"message": "bad"}]}))
    try:
        await endpoint.create([], "auto")
    except endpoints.GeminiInteractionError as exc:
        assert "bad" in str(exc)
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
    await tester.test(_test_tool_image_message_is_merged_into_function_result, "工具图片并入函数结果")
    await tester.test(_test_thinking_level_mapping, "思考强度映射为 thinking_level")
    await tester.test(_test_request_payload, "请求载荷包含模型、工具与生成配置")
    await tester.test(
        _test_request_omits_default_sampling_and_disabled_thinking,
        "默认采样与关闭思考时省略对应字段",
    )
    await tester.test(_test_response_is_parsed, "响应解析文本、工具调用与用量")
    await tester.test(_test_rate_limit_is_retryable, "429 归入可重试异常")
    await tester.test(_test_api_error_is_raised, "其他 HTTP 错误抛出端点异常")
    await tester.test(_test_failed_status_is_raised, "失败状态抛出端点异常")
    return tester
