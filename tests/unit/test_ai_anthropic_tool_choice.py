"""modules.ai Anthropic 端点 tool_choice 线格式单元测试。"""

from types import SimpleNamespace

from core.tester import func_case, Tester
from modules.ai import endpoints


class _Stop(Exception):
    """捕获请求参数后中断 create 流程。"""


async def _capture_tool_choice(tool_choice: str) -> dict:
    endpoint = endpoints.AnthropicEndpoint("http://127.0.0.1", "k", "claude-sonnet-5-5")
    captured = {}

    class _Messages:
        async def create(self, **kwargs):
            captured.update(kwargs)
            raise _Stop

    endpoint.client = SimpleNamespace(messages=_Messages())
    try:
        await endpoint.create([{"role": "user", "content": "hi"}], tool_choice)
    except _Stop:
        pass
    return captured


async def _test_auto_is_sent_as_object():
    captured = await _capture_tool_choice("auto")
    assert captured["tool_choice"] == {"type": "auto"}
    return True


@func_case
async def test_ai_anthropic_tool_choice(tester: Tester):
    """modules.ai: Anthropic 端点下发对象形式的 tool_choice"""
    await tester.test(_test_auto_is_sent_as_object, "auto 包装为对象")
    return tester
