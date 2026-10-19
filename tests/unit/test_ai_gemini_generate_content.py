"""modules.ai Gemini GenerateContent API 端点单元测试。"""

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
        self.response = response or _FakeResponse(
            {"candidates": [{"content": {"role": "model", "parts": [{"text": "ok"}]}}]}
        )
        self.requests = []

    async def post(self, url, json=None):
        self.requests.append((url, json))
        return self.response


def _build_endpoint(model_name="gemini-3.5-flash", generation=None, response=None):
    endpoint = endpoints.GeminiGenerateContentEndpoint(
        "https://generativelanguage.googleapis.com/v1beta",
        "key",
        model_name,
        generation,
    )
    client = _FakeClient(response)
    endpoint.client = client
    return endpoint, client


def _test_build_endpoint():
    endpoint = endpoints.build_endpoint(
        "gemini",
        "https://generativelanguage.googleapis.com/v1beta",
        "key",
        "models/gemini-3.5-flash",
    )
    assert isinstance(endpoint, endpoints.GeminiGenerateContentEndpoint)
    assert endpoint.url == "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent"
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
    system, contents = endpoints._messages_to_generate_content(messages)
    assert system == "sys1\n\nsys2"
    assert contents == [
        {
            "role": "user",
            "parts": [{"text": "hi"}, {"inlineData": {"mimeType": "image/png", "data": "AAAA"}}],
        },
        {
            "role": "model",
            "parts": [{"text": "answer"}, {"functionCall": {"name": "search_web", "args": {"query": "x"}}}],
        },
        {
            "role": "user",
            "parts": [{"functionResponse": {"name": "search_web", "response": {"result": "result"}}}],
        },
    ]
    return True


def _test_raw_parts_are_replayed():
    raw_parts = [
        {"text": "thinking", "thought": True, "thoughtSignature": "sig1"},
        {
            "functionCall": {"id": "fc_1", "name": "search_web", "args": {"query": "x"}},
            "thoughtSignature": "sig2",
        },
    ]
    messages = [
        {
            "role": "assistant",
            "content": "ignored",
            "tool_calls": [{"id": "fc_1", "type": "function", "function": {"name": "search_web", "arguments": "{}"}}],
            "_gemini_parts": raw_parts,
            "_gemini_call_api_ids": {"fc_1": "fc_1"},
        },
        {"role": "tool", "tool_call_id": "fc_1", "content": "result"},
    ]
    _, contents = endpoints._messages_to_generate_content(messages)
    assert contents == [
        {"role": "model", "parts": raw_parts},
        {
            "role": "user",
            "parts": [
                {
                    "functionResponse": {
                        "name": "search_web",
                        "response": {"result": "result"},
                        "id": "fc_1",
                    }
                }
            ],
        },
    ]
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
        },
        {"role": "tool", "tool_call_id": "call_1", "content": "first"},
        {"role": "tool", "tool_call_id": "call_2", "content": "second"},
    ]
    _, contents = endpoints._messages_to_generate_content(messages)
    assert contents[-1] == {
        "role": "user",
        "parts": [
            {"functionResponse": {"name": "search_web", "response": {"result": "first"}}},
            {"functionResponse": {"name": "fetch_webpage", "response": {"result": "second"}}},
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
    _, contents = endpoints._messages_to_generate_content(messages)
    assert contents[-1] == {
        "role": "user",
        "parts": [
            {"functionResponse": {"name": "generate_image", "response": {"result": "done"}}},
            {"text": "images"},
            {"inlineData": {"mimeType": "image/png", "data": "AAAA"}},
        ],
    }
    return True


def _test_thinking_config():
    assert endpoints._supports_thinking_level("gemini-3.5-flash")
    assert endpoints._supports_thinking_level("gemini-4-argon")
    assert endpoints._supports_thinking_level("gemini-flash-latest")
    assert not endpoints._supports_thinking_level("gemini-2.5-flash")
    assert endpoints._thinking_config("low", "gemini-3.5-flash") == {"thinkingLevel": "LOW"}
    assert endpoints._thinking_config("xhigh", "gemini-3.5-flash") == {"thinkingLevel": "HIGH"}
    assert endpoints._thinking_config("low", "gemini-2.5-flash") == {"thinkingBudget": 1024}
    assert endpoints._thinking_config("medium", "gemini-2.5-pro") == {"thinkingBudget": 8192}
    assert endpoints._thinking_config("none", "gemini-3.5-flash") is None
    assert endpoints._thinking_config("none", "gemini-2.5-flash") == {"thinkingBudget": 0}
    assert endpoints._thinking_config("none", "gemini-2.5-pro") is None
    assert endpoints._thinking_config("low", "gemini-2.0-flash") is None
    assert endpoints._thinking_config("low", "gemma-4-31b-it") is None
    return True


async def _test_request_payload():
    endpoint, client = _build_endpoint(
        generation={"temperature": 0.2, "top_p": 0.9, "top_logprobs": 5, "reasoning_effort": "xhigh"}
    )
    await endpoint.create(
        [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": [{"type": "text", "text": "hi"}]},
        ],
        "auto",
    )
    url, payload = client.requests[0]
    assert url == "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent"
    assert payload["systemInstruction"] == {"parts": [{"text": "sys"}]}
    assert payload["contents"] == [{"role": "user", "parts": [{"text": "hi"}]}]
    declaration = payload["tools"][0]["functionDeclarations"][0]
    assert declaration["name"]
    assert "parameters" in declaration
    assert payload["toolConfig"] == {"functionCallingConfig": {"mode": "AUTO"}}
    assert payload["generationConfig"] == {
        "maxOutputTokens": endpoints.base.max_tokens,
        "frequencyPenalty": endpoints.base.frequency_penalty,
        "presencePenalty": endpoints.base.presence_penalty,
        "temperature": 0.2,
        "topP": 0.9,
        "responseLogprobs": True,
        "logprobs": 5,
        "thinkingConfig": {"thinkingLevel": "HIGH"},
    }
    return True


async def _test_request_omits_defaults():
    endpoint, client = _build_endpoint(
        model_name="gemini-2.5-flash",
        generation={"temperature": 1, "top_p": 1, "top_logprobs": -1, "reasoning_effort": "none"},
    )
    await endpoint.create([{"role": "user", "content": "hi"}], "none")
    _, payload = client.requests[0]
    config = payload["generationConfig"]
    assert payload["toolConfig"] == {"functionCallingConfig": {"mode": "NONE"}}
    assert "temperature" not in config
    assert "topP" not in config
    assert "responseLogprobs" not in config
    assert "logprobs" not in config
    assert config["thinkingConfig"] == {"thinkingBudget": 0}
    return True


async def _test_response_is_parsed():
    parts = [
        {"text": "thinking", "thought": True, "thoughtSignature": "sig1"},
        {"text": "hello "},
        {"text": "world"},
        {
            "functionCall": {"id": "fc_1", "name": "search_web", "args": {"query": "x"}},
            "thoughtSignature": "sig2",
        },
    ]
    response = _FakeResponse(
        {
            "candidates": [{"content": {"role": "model", "parts": parts}, "finishReason": "STOP"}],
            "usageMetadata": {
                "promptTokenCount": 100,
                "cachedContentTokenCount": 40,
                "candidatesTokenCount": 10,
                "thoughtsTokenCount": 5,
            },
        }
    )
    endpoint, _ = _build_endpoint(response=response)
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
    assert result.assistant_message["_gemini_parts"] == parts
    assert result.assistant_message["_gemini_call_api_ids"] == {"fc_1": "fc_1"}
    return True


async def _test_response_without_function_call_id():
    response = _FakeResponse(
        {
            "candidates": [
                {
                    "content": {
                        "role": "model",
                        "parts": [{"functionCall": {"name": "search_web", "args": {}}}],
                    },
                    "finishReason": "STOP",
                }
            ]
        }
    )
    endpoint, _ = _build_endpoint(model_name="gemini-2.5-flash", response=response)
    result = await endpoint.create([{"role": "user", "content": "hi"}], "auto")
    call_id = result.tool_calls[0].id
    assert call_id.startswith("call_")
    assert result.assistant_message["_gemini_call_api_ids"] == {call_id: None}
    _, contents = endpoints._messages_to_generate_content(
        [
            result.assistant_message,
            {"role": "tool", "tool_call_id": call_id, "content": "result"},
        ]
    )
    assert "id" not in contents[-1]["parts"][0]["functionResponse"]
    return True


async def _test_rate_limit_is_retryable():
    endpoint, _ = _build_endpoint(response=_FakeResponse(status_code=429, text="rate limited"))
    try:
        await endpoint.create([], "auto")
    except endpoints.GeminiGenerateContentRateLimitError as exc:
        assert "429" in str(exc)
    else:
        raise AssertionError("expected rate limit error")
    assert endpoints.GeminiGenerateContentRateLimitError in endpoints.RETRYABLE_EXCEPTIONS
    return True


async def _test_api_error_is_raised():
    endpoint, _ = _build_endpoint(response=_FakeResponse(status_code=400, text="bad request"))
    try:
        await endpoint.create([], "auto")
    except endpoints.GeminiGenerateContentError as exc:
        assert "400" in str(exc)
    else:
        raise AssertionError("expected api error")
    return True


async def _test_blocked_prompt_is_raised():
    response = _FakeResponse({"promptFeedback": {"blockReason": "SAFETY"}})
    endpoint, _ = _build_endpoint(response=response)
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
    await tester.test(_test_parallel_tool_results_are_merged, "并行工具结果合并为一轮")
    await tester.test(_test_tool_image_message_is_merged, "工具图片并入函数结果轮次")
    await tester.test(_test_thinking_config, "思考配置按模型代次映射")
    await tester.test(_test_request_payload, "请求载荷包含模型、工具与生成配置")
    await tester.test(_test_request_omits_defaults, "默认采样与关闭思考时省略对应字段")
    await tester.test(_test_response_is_parsed, "响应解析文本、工具调用与用量")
    await tester.test(_test_response_without_function_call_id, "缺少函数调用 ID 时生成内部 ID")
    await tester.test(_test_rate_limit_is_retryable, "429 归入可重试异常")
    await tester.test(_test_api_error_is_raised, "其他 HTTP 错误抛出端点异常")
    await tester.test(_test_blocked_prompt_is_raised, "提示被拦截时抛出端点异常")
    return tester
