"""modules.ai 生成参数（采样与思考强度）按模型覆盖的单元测试。"""

from types import SimpleNamespace
from unittest.mock import patch

from core.tester import func_case, Tester
from modules.ai import endpoints, setting


class _Stop(Exception):
    """捕获请求参数后中断 create 流程。"""


def _test_qwen_thinking_support_detection():
    assert endpoints._supports_qwen_thinking("qwen3.8-max")
    assert endpoints._supports_qwen_thinking("Qwen-Plus-latest")
    assert endpoints._supports_qwen_thinking("qwen/qwen3.8-flash")
    assert endpoints._supports_qwen_thinking("qwen-flash-2025-07-28")
    # 仅思考模式或非混合思考模式的千问模型不接受 enable_thinking
    assert not endpoints._supports_qwen_thinking("qwen-max")
    assert not endpoints._supports_qwen_thinking("qwen2.5-72b-instruct")
    assert not endpoints._supports_qwen_thinking("qwq-32b")
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
        patch.object(endpoints.base, "temperature", 0.5),
        patch.object(endpoints.base, "top_p", 0.6),
        patch.object(endpoints.base, "top_logprobs", -1),
        patch.object(endpoints.base, "reasoning_effort", "low"),
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
        patch.object(endpoints.base, "temperature", -1.0),
        patch.object(endpoints.base, "top_p", -0.5),
    ):
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
        patch.object(endpoints.base, "temperature", 1.0),
        patch.object(endpoints.base, "top_p", 1.0),
    ):
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
    with patch.object(endpoints.base, "reasoning_effort", "none"):
        try:
            await endpoint.create([], "auto")
        except _Stop:
            pass
    assert "reasoning_effort" not in captured
    return True


async def _test_completions_enables_qwen_thinking():
    endpoint = endpoints.OpenAICompletionsEndpoint("http://127.0.0.1", "k", "qwen3.8-max")
    captured = {}

    class _Completions:
        async def create(self, **kwargs):
            captured.update(kwargs)
            raise _Stop

    endpoint.client = SimpleNamespace(chat=SimpleNamespace(completions=_Completions()))
    with patch.object(endpoints.base, "reasoning_effort", "high"):
        try:
            await endpoint.create([], "auto")
        except _Stop:
            pass
    assert captured["extra_body"] == {"enable_thinking": True}
    return True


async def _test_completions_disables_qwen_thinking():
    endpoint = endpoints.OpenAICompletionsEndpoint("http://127.0.0.1", "k", "qwen-plus")
    captured = {}

    class _Completions:
        async def create(self, **kwargs):
            captured.update(kwargs)
            raise _Stop

    endpoint.client = SimpleNamespace(chat=SimpleNamespace(completions=_Completions()))
    with patch.object(endpoints.base, "reasoning_effort", "none"):
        try:
            await endpoint.create([], "auto")
        except _Stop:
            pass
    assert captured["extra_body"] == {"enable_thinking": False}
    return True


async def _test_completions_skips_qwen_switch_for_other_models():
    endpoint = endpoints.OpenAICompletionsEndpoint("http://127.0.0.1", "k", "gpt-5.4")
    captured = {}

    class _Completions:
        async def create(self, **kwargs):
            captured.update(kwargs)
            raise _Stop

    endpoint.client = SimpleNamespace(chat=SimpleNamespace(completions=_Completions()))
    with patch.object(endpoints.base, "reasoning_effort", "high"):
        try:
            await endpoint.create([], "auto")
        except _Stop:
            pass
    assert "extra_body" not in captured
    return True


async def _test_completions_keeps_deepseek_thinking():
    endpoint = endpoints.OpenAICompletionsEndpoint("http://127.0.0.1", "k", "deepseek-flash")
    captured = {}

    class _Completions:
        async def create(self, **kwargs):
            captured.update(kwargs)
            raise _Stop

    endpoint.client = SimpleNamespace(chat=SimpleNamespace(completions=_Completions()))
    with patch.object(endpoints.base, "reasoning_effort", "none"):
        try:
            await endpoint.create([], "auto")
        except _Stop:
            pass
    assert captured["extra_body"] == {"thinking": {"type": "disabled"}}
    return True


def _test_anthropic_thinking_adaptive_when_enabled():
    assert endpoints._anthropic_thinking("high") == {"type": "adaptive"}
    # minimal 不映射到 output_config，但仍开启思考
    assert endpoints._anthropic_thinking("minimal") == {"type": "adaptive"}
    return True


async def _test_anthropic_uses_adaptive_thinking():
    endpoint = endpoints.AnthropicEndpoint("http://127.0.0.1", "k", "claude-sonnet-5-5")
    captured = {}

    class _Messages:
        async def create(self, **kwargs):
            captured.update(kwargs)
            raise _Stop

    endpoint.client = SimpleNamespace(messages=_Messages())
    with patch.object(endpoints.base, "reasoning_effort", "high"):
        try:
            await endpoint.create([{"role": "user", "content": "hi"}], "auto")
        except _Stop:
            pass
    assert captured["thinking"] == {"type": "adaptive"}
    assert captured["output_config"] == {"effort": "high"}
    return True


async def _test_anthropic_omits_thinking_when_none():
    endpoint = endpoints.AnthropicEndpoint("http://127.0.0.1", "k", "claude-sonnet-5-5")
    captured = {}

    class _Messages:
        async def create(self, **kwargs):
            captured.update(kwargs)
            raise _Stop

    endpoint.client = SimpleNamespace(messages=_Messages())
    with patch.object(endpoints.base, "reasoning_effort", "none"):
        try:
            await endpoint.create([{"role": "user", "content": "hi"}], "auto")
        except _Stop:
            pass
    assert "thinking" not in captured
    assert "output_config" not in captured
    return True


@func_case
async def test_ai_reasoning_effort(tester: Tester):
    """modules.ai: 采样、思考强度与对数概率支持按模型覆盖或空值省略"""
    await tester.test(_test_qwen_thinking_support_detection, "仅混合思考模式的千问模型支持 enable_thinking")
    await tester.test(_test_generation_extracts_overrides, "仅提取已配置的覆盖项")
    await tester.test(_test_completions_uses_generation_overrides, "模型覆盖项透传给端点")
    await tester.test(_test_completions_uses_module_defaults_when_absent, "未配置时回落模块默认")
    await tester.test(_test_completions_omits_null_sampling_params, "空值采样参数不下发")
    await tester.test(_test_completions_forwards_negative_module_defaults, "负数模块采样参数照常下发")
    await tester.test(_test_completions_omits_default_module_sampling, "默认值 1 的模块采样参数不下发")
    await tester.test(_test_completions_uses_top_logprobs, "Chat Completions 请求对数概率")
    await tester.test(_test_responses_uses_top_logprobs, "Responses 请求对数概率")
    await tester.test(
        _test_completions_omits_reasoning_effort_when_none,
        "Chat Completions 端点在 none 时省略 reasoning_effort",
    )
    await tester.test(_test_completions_enables_qwen_thinking, "Chat Completions 端点开启千问思考模式")
    await tester.test(_test_completions_disables_qwen_thinking, "Chat Completions 端点关闭千问思考模式")
    await tester.test(_test_completions_skips_qwen_switch_for_other_models, "非千问模型不传 enable_thinking")
    await tester.test(_test_completions_keeps_deepseek_thinking, "DeepSeek 仍使用 thinking.type")
    await tester.test(_test_anthropic_thinking_adaptive_when_enabled, "Anthropic 开启思考时使用 adaptive")
    await tester.test(_test_anthropic_uses_adaptive_thinking, "Anthropic 端点开启思考并透传思考强度")
    await tester.test(_test_anthropic_omits_thinking_when_none, "Anthropic 端点未开启思考时不透传 thinking")
    return tester
