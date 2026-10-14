"""modules.ai 生成参数（采样与思考强度）按模型覆盖的单元测试。"""

from types import SimpleNamespace
from unittest.mock import patch

from core.tester import func_case, Tester
from modules.ai import endpoints, setting


class _Stop(Exception):
    """捕获请求参数后中断 create 流程。"""


def _test_none_maps_to_disabled():
    assert endpoints._openai_effort("none") is None
    return True


def _test_supported_value_passes_through():
    assert endpoints._openai_effort("high") == "high"
    return True


def _test_generation_extracts_overrides():
    llm = {"temperature": 0.2, "top_p": 0.8, "top_logprobs": 5, "reasoning_effort": "high", "name": "x"}
    assert setting.get_llm_generation(llm) == {
        "temperature": 0.2,
        "top_p": 0.8,
        "top_logprobs": 5,
        "reasoning_effort": "high",
    }
    assert setting.get_llm_generation({"name": "x"}) == {}
    # 显式 null 保留为空值，用于指示该参数不下发
    assert setting.get_llm_generation({"temperature": None, "name": "x"}) == {"temperature": None}
    return True


async def _test_completions_uses_generation_overrides():
    generation = {"temperature": 0.2, "top_p": 0.8, "reasoning_effort": "high"}
    endpoint = endpoints.OpenAICompletionsEndpoint("http://127.0.0.1", "k", "gpt-5.4", generation)
    captured = {}

    class _Completions:
        async def create(self, **kwargs):
            captured.update(kwargs)
            raise _Stop

    endpoint.client = SimpleNamespace(chat=SimpleNamespace(completions=_Completions()))
    try:
        await endpoint.create([], "auto")
    except _Stop:
        pass
    assert captured["temperature"] == 0.2
    assert captured["top_p"] == 0.8
    assert captured["reasoning_effort"] == "high"
    return True


async def _test_completions_uses_module_defaults_when_absent():
    endpoint = endpoints.OpenAICompletionsEndpoint("http://127.0.0.1", "k", "gpt-5.4")
    captured = {}

    class _Completions:
        async def create(self, **kwargs):
            captured.update(kwargs)
            raise _Stop

    endpoint.client = SimpleNamespace(chat=SimpleNamespace(completions=_Completions()))
    with (
        patch.object(endpoints, "temperature", 0.5),
        patch.object(endpoints, "top_p", 0.6),
        patch.object(endpoints, "top_logprobs", -1),
        patch.object(endpoints, "reasoning_effort", "low"),
    ):
        try:
            await endpoint.create([], "auto")
        except _Stop:
            pass
    assert captured["temperature"] == 0.5
    assert captured["top_p"] == 0.6
    assert captured["reasoning_effort"] == "low"
    # 模块默认的 top_logprobs 为负数，表示不请求对数概率
    assert "logprobs" not in captured
    assert "top_logprobs" not in captured
    return True


async def _test_completions_omits_null_sampling_params():
    generation = {"temperature": None, "top_p": None, "top_logprobs": None}
    endpoint = endpoints.OpenAICompletionsEndpoint("http://127.0.0.1", "k", "gpt-5.4", generation)
    captured = {}

    class _Completions:
        async def create(self, **kwargs):
            captured.update(kwargs)
            raise _Stop

    endpoint.client = SimpleNamespace(chat=SimpleNamespace(completions=_Completions()))
    try:
        await endpoint.create([], "auto")
    except _Stop:
        pass
    assert "temperature" not in captured
    assert "top_p" not in captured
    assert "logprobs" not in captured
    assert "top_logprobs" not in captured
    return True


async def _test_completions_forwards_negative_module_defaults():
    endpoint = endpoints.OpenAICompletionsEndpoint("http://127.0.0.1", "k", "gpt-5.4")
    captured = {}

    class _Completions:
        async def create(self, **kwargs):
            captured.update(kwargs)
            raise _Stop

    endpoint.client = SimpleNamespace(chat=SimpleNamespace(completions=_Completions()))
    with (
        patch.object(endpoints, "temperature", -1.0),
        patch.object(endpoints, "top_p", -0.5),
    ):
        try:
            await endpoint.create([], "auto")
        except _Stop:
            pass
    assert captured["temperature"] == -1.0
    assert captured["top_p"] == -0.5
    return True


async def _test_completions_forwards_negative_generation_overrides():
    generation = {"temperature": -1.0, "top_p": -0.5}
    endpoint = endpoints.OpenAICompletionsEndpoint("http://127.0.0.1", "k", "gpt-5.4", generation)
    captured = {}

    class _Completions:
        async def create(self, **kwargs):
            captured.update(kwargs)
            raise _Stop

    endpoint.client = SimpleNamespace(chat=SimpleNamespace(completions=_Completions()))
    try:
        await endpoint.create([], "auto")
    except _Stop:
        pass
    assert captured["temperature"] == -1.0
    assert captured["top_p"] == -0.5
    return True


async def _test_completions_omits_default_module_sampling():
    endpoint = endpoints.OpenAICompletionsEndpoint("http://127.0.0.1", "k", "gpt-5.4")
    captured = {}

    class _Completions:
        async def create(self, **kwargs):
            captured.update(kwargs)
            raise _Stop

    endpoint.client = SimpleNamespace(chat=SimpleNamespace(completions=_Completions()))
    with (
        patch.object(endpoints, "temperature", 1.0),
        patch.object(endpoints, "top_p", 1.0),
    ):
        try:
            await endpoint.create([], "auto")
        except _Stop:
            pass
    assert "temperature" not in captured
    assert "top_p" not in captured
    return True


async def _test_completions_omits_default_generation_overrides():
    generation = {"temperature": 1.0, "top_p": 1.0}
    endpoint = endpoints.OpenAICompletionsEndpoint("http://127.0.0.1", "k", "gpt-5.4", generation)
    captured = {}

    class _Completions:
        async def create(self, **kwargs):
            captured.update(kwargs)
            raise _Stop

    endpoint.client = SimpleNamespace(chat=SimpleNamespace(completions=_Completions()))
    try:
        await endpoint.create([], "auto")
    except _Stop:
        pass
    assert "temperature" not in captured
    assert "top_p" not in captured
    return True


async def _test_completions_uses_top_logprobs():
    endpoint = endpoints.OpenAICompletionsEndpoint("http://127.0.0.1", "k", "gpt-5.4", {"top_logprobs": 5})
    captured = {}

    class _Completions:
        async def create(self, **kwargs):
            captured.update(kwargs)
            raise _Stop

    endpoint.client = SimpleNamespace(chat=SimpleNamespace(completions=_Completions()))
    try:
        await endpoint.create([], "auto")
    except _Stop:
        pass
    assert captured["logprobs"] is True
    assert captured["top_logprobs"] == 5
    return True


async def _test_responses_uses_top_logprobs():
    endpoint = endpoints.OpenAIResponsesEndpoint("http://127.0.0.1", "k", "gpt-5.4", {"top_logprobs": 3})
    captured = {}

    class _Responses:
        async def create(self, **kwargs):
            captured.update(kwargs)
            raise _Stop

    endpoint.client = SimpleNamespace(responses=_Responses())
    try:
        await endpoint.create([], "auto")
    except _Stop:
        pass
    assert captured["top_logprobs"] == 3
    assert captured["include"] == ["message.output_text.logprobs"]
    return True


async def _test_completions_omits_reasoning_effort_when_none():
    endpoint = endpoints.OpenAICompletionsEndpoint("http://127.0.0.1", "k", "gpt-5.4")
    captured = {}

    class _Completions:
        async def create(self, **kwargs):
            captured.update(kwargs)
            raise _Stop

    endpoint.client = SimpleNamespace(chat=SimpleNamespace(completions=_Completions()))
    with patch.object(endpoints, "reasoning_effort", "none"):
        try:
            await endpoint.create([], "auto")
        except _Stop:
            pass
    assert "reasoning_effort" not in captured
    return True


async def _test_completions_keeps_reasoning_effort_when_set():
    endpoint = endpoints.OpenAICompletionsEndpoint("http://127.0.0.1", "k", "gpt-5.4")
    captured = {}

    class _Completions:
        async def create(self, **kwargs):
            captured.update(kwargs)
            raise _Stop

    endpoint.client = SimpleNamespace(chat=SimpleNamespace(completions=_Completions()))
    with patch.object(endpoints, "reasoning_effort", "high"):
        try:
            await endpoint.create([], "auto")
        except _Stop:
            pass
    assert captured["reasoning_effort"] == "high"
    return True


@func_case
async def test_ai_reasoning_effort(tester: Tester):
    """modules.ai: 采样、思考强度与对数概率支持按模型覆盖或空值省略"""
    await tester.test(_test_none_maps_to_disabled, "none 归一化为 None")
    await tester.test(_test_supported_value_passes_through, "受支持取值原样透传")
    await tester.test(_test_generation_extracts_overrides, "仅提取已配置的覆盖项")
    await tester.test(_test_completions_uses_generation_overrides, "模型覆盖项透传给端点")
    await tester.test(_test_completions_uses_module_defaults_when_absent, "未配置时回落模块默认")
    await tester.test(_test_completions_omits_null_sampling_params, "空值采样参数不下发")
    await tester.test(_test_completions_forwards_negative_module_defaults, "负数模块采样参数照常下发")
    await tester.test(_test_completions_forwards_negative_generation_overrides, "负数模型覆盖采样参数照常下发")
    await tester.test(_test_completions_omits_default_module_sampling, "默认值 1 的模块采样参数不下发")
    await tester.test(_test_completions_omits_default_generation_overrides, "默认值 1 的模型覆盖采样参数不下发")
    await tester.test(_test_completions_uses_top_logprobs, "Chat Completions 请求对数概率")
    await tester.test(_test_responses_uses_top_logprobs, "Responses 请求对数概率")
    await tester.test(
        _test_completions_omits_reasoning_effort_when_none,
        "Chat Completions 端点在 none 时省略 reasoning_effort",
    )
    await tester.test(
        _test_completions_keeps_reasoning_effort_when_set,
        "Chat Completions 端点在非 none 时保留 reasoning_effort",
    )
    return tester
