"""modules.ai.llm 系统提示中的会话语言标记单元测试。"""

from types import SimpleNamespace
from unittest.mock import patch

from core.i18n import Locale
from core.tester import func_case, Tester
from modules.ai import llm
from modules.ai.endpoints import ParsedResult


class _FakeClient:
    def __init__(self, captured: dict):
        self._captured = captured

    async def create(self, messages, tool_choice=None):
        self._captured["messages"] = messages
        return ParsedResult(
            text="ok",
            tool_calls=[],
            input_tokens=1,
            output_tokens=1,
            cache_read_tokens=0,
            cache_write_tokens=0,
            assistant_message={"role": "assistant", "content": "ok"},
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


async def _test_language_marker_follows_session_info():
    captured = {}
    with patch.object(llm, "build_endpoint", lambda *args, **kwargs: _FakeClient(captured)):
        await llm.ask_llm(_session("zh_cn"), "hi", "m", "http://127.0.0.1", "k")

    system_messages = [message["content"] for message in captured["messages"] if message["role"] == "system"]
    language_message = next(message for message in system_messages if message.startswith("Session language:"))
    assert f"{Locale('zh_cn').t('language')} (zh_cn)" in language_message
    # 无法判断输入语言时按会话语言输出
    assert "cannot be determined" in language_message
    assert "session language" in language_message
    return True


async def _test_language_marker_switches_with_locale():
    captured = {}
    with patch.object(llm, "build_endpoint", lambda *args, **kwargs: _FakeClient(captured)):
        await llm.ask_llm(_session("en_us"), "hi", "m", "http://127.0.0.1", "k")

    system_messages = [message["content"] for message in captured["messages"] if message["role"] == "system"]
    language_message = next(message for message in system_messages if message.startswith("Session language:"))
    assert "(en_us)" in language_message
    return True


@func_case
async def test_ai_language_prompt(tester: Tester):
    """modules.ai.llm: 会话语言标记与语言回退规则测试"""
    await tester.test(_test_language_marker_follows_session_info, "系统提示带会话语言标记与回退规则")
    await tester.test(_test_language_marker_switches_with_locale, "系统提示语言标记跟随会话语言")
    return tester
