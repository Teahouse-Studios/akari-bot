"""modules.ai.llm 系统提示中的会话语言标记与指令模板渲染单元测试。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from core.builtins.utils import command_prefix
from core.i18n import Locale
from core.tester import func_case, Tester
from modules.ai import llm
from modules.ai.endpoints import ParsedResult


class _FakeClient:
    def __init__(self, captured: dict, text: str = "ok"):
        self._captured = captured
        self._text = text

    async def create(self, messages, tool_choice=None):
        self._captured["messages"] = messages
        return ParsedResult(
            text=self._text,
            tool_calls=[],
            input_tokens=1,
            output_tokens=1,
            cache_read_tokens=0,
            cache_write_tokens=0,
            assistant_message={"role": "assistant", "content": self._text},
        )


def _session(locale_name: str):
    session_info = SimpleNamespace(
        locale=Locale(locale_name),
        _tz_offset="+0",
        sender_union_info=SimpleNamespace(sender_data={}),
        support_markdown=False,
        support_markdown_extension=False,
        support_image=False,
        require_check_dirty_words=False,
    )
    return SimpleNamespace(session_info=session_info)


async def _capture_instructions_message(locale_name: str) -> str:
    captured = {}
    with patch.object(llm, "build_endpoint", lambda *args, **kwargs: _FakeClient(captured)):
        await llm.ask_llm(_session(locale_name), "hi", "m", "http://127.0.0.1", "k")
    return next(message["content"] for message in captured["messages"] if message["role"] == "system")


async def _test_language_marker_follows_session_info():
    instructions_message = await _capture_instructions_message("zh_cn")
    assert f"{Locale('zh_cn').t('language')} (zh_cn)" in instructions_message
    # 无法判断输入语言时按会话语言输出
    assert "cannot be determined" in instructions_message
    assert "session language" in instructions_message
    return True


async def _test_language_marker_switches_with_locale():
    instructions_message = await _capture_instructions_message("en_us")
    assert "(en_us)" in instructions_message
    return True


async def _test_command_prefix_is_substituted():
    instructions_message = await _capture_instructions_message("zh_cn")
    assert "${prefix}" not in instructions_message
    assert f"`{command_prefix[0]}help`" in instructions_message
    return True


async def _test_latex_dollars_preserved():
    instructions_message = await _capture_instructions_message("zh_cn")
    assert "$$...$$" in instructions_message
    return True


async def _test_severe_refusal_uses_rickroll():
    captured = {}
    dirty_check = AsyncMock()
    with (
        patch.object(
            llm,
            "build_endpoint",
            lambda *args, **kwargs: _FakeClient(captured, " \nSEVERE_REFUSAL_RICKROLL\n "),
        ),
        patch.object(llm, "check", dirty_check),
        patch.object(llm, "rickroll", return_value="rickroll output"),
    ):
        chain, *_ = await llm.ask_llm(_session("zh_cn"), "hi", "m", "http://127.0.0.1", "k")

    assert len(chain) == 1
    assert chain[0].text == "rickroll output"
    dirty_check.assert_not_awaited()
    return True


@func_case
async def test_ai_language_prompt(tester: Tester):
    """modules.ai.llm: 指令模板渲染、会话语言标记与命令前缀替换测试"""
    await tester.test(_test_language_marker_follows_session_info, "系统提示带会话语言标记与回退规则")
    await tester.test(_test_language_marker_switches_with_locale, "系统提示语言标记跟随会话语言")
    await tester.test(_test_command_prefix_is_substituted, "系统提示替换命令前缀占位符")
    await tester.test(_test_latex_dollars_preserved, "指令模板保留 LaTeX 美元符号")
    await tester.test(_test_severe_refusal_uses_rickroll, "严重拒绝标记直接输出 Rickroll")
    return tester
