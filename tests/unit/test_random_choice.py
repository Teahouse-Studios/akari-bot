"""modules.random.choice AI 选择流程单元测试。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from core.builtins.bot import Bot
from core.constants import SessionFinished
from core.i18n import Locale
from core.tester import func_case, Tester
from modules.random import choice

_ZH_CN_REFUSAL = Locale("zh_cn").t(choice.REFUSAL_KEY, locale_failed_prompt=False)


class _FakeMessageSession:
    def __init__(self, locale_name: str = "zh_cn"):
        self.session_info = SimpleNamespace(locale=Locale(locale_name))
        self.sent = []

    async def finish(self, message=None):
        self.sent.append(message)
        raise SessionFinished


def _test_build_choice_prompt():
    prompt = choice.build_choice_prompt(["apple", "banana"])
    # 提示词文案取自 data 目录的模板，代码侧只负责填入候选元素
    header = choice.CHOICE_PROMPT.split("${candidates}")[0].strip()
    assert header and header in prompt
    assert "1. apple" in prompt
    assert "2. banana" in prompt
    assert "${candidates}" not in prompt
    return True


def _test_build_instructions_injects_localized_refusal():
    instructions = choice.build_instructions(_ZH_CN_REFUSAL)
    assert _ZH_CN_REFUSAL in instructions
    assert "${refusal}" not in instructions
    return True


def _test_refusal_texts_come_from_locales():
    texts = choice.get_refusal_texts(Locale("en_us"))
    assert _ZH_CN_REFUSAL in texts
    assert all(text and choice.UNTRANSLATED_MARK not in text for text in texts)
    # 提示词中不得再硬编码任一语言的拒答语句
    assert _ZH_CN_REFUSAL not in choice.CHOICE_INSTRUCTIONS
    return True


def _test_instructions_cover_randomness_and_brand_safety():
    instructions = choice.CHOICE_INSTRUCTIONS
    # 随机性：要求任意挑选，并明确排除「择优」倾向
    assert "arbitrarily" in instructions
    assert "not the best" in instructions
    # 品牌安全：明确覆盖对机器人及其开发方的侮辱，含「小可是…」句式
    assert "小可是" in instructions
    assert "AkariBot" in instructions and "Teahouse Studios" in instructions
    return True


def _test_match_choice():
    choices = ["apple", "banana"]
    assert choice.match_choice("apple", choices) == "apple"
    assert choice.match_choice("1. banana", choices) == "banana"
    assert choice.match_choice("2、apple", choices) == "apple"
    # 模型添加前后缀时按元素原文回填
    assert choice.match_choice("我选择 banana。", choices) == "banana"
    assert choice.match_choice("apple or banana?", choices) is None
    # 互为子串的候选保留更长的那个
    assert choice.match_choice("I choose apple", ["app", "apple"]) == "apple"
    return True


async def _test_ask_ai_choice_unmatched_reply():
    msg = _FakeMessageSession()
    hook_result = SimpleNamespace(status=choice.STATUS_OK, text="这两个我都不想选", petal=0, chain=[])
    with patch.object(Bot.Hook, "trigger", new=AsyncMock(return_value=hook_result)):
        try:
            await choice.ask_ai_choice(msg, ["apple", "banana"])
        except SessionFinished:
            pass
        else:
            return False
    return len(msg.sent) == 1 and msg.sent[0].key == choice.REFUSAL_KEY


async def _test_ask_ai_choice_fallback_without_hook():
    msg = _FakeMessageSession()
    with patch.object(Bot.Hook, "trigger", new=AsyncMock(side_effect=ValueError("Invalid module name ai"))):
        assert await choice.ask_ai_choice(msg, ["apple", "banana"]) is None
    return True


async def _test_ask_ai_choice_without_prompt_text():
    msg = _FakeMessageSession()
    trigger = AsyncMock()
    with patch.object(choice, "CHOICE_PROMPT", ""), patch.object(Bot.Hook, "trigger", new=trigger):
        assert await choice.ask_ai_choice(msg, ["apple", "banana"]) is None
    return trigger.await_count == 0


async def _test_ask_ai_choice_fallback_on_hook_failure():
    msg = _FakeMessageSession()
    with patch.object(Bot.Hook, "trigger", new=AsyncMock(side_effect=RuntimeError("boom"))):
        assert await choice.ask_ai_choice(msg, ["apple", "banana"]) is None
    return True


async def _test_ask_ai_choice_fallback_when_not_executed():
    msg = _FakeMessageSession()
    with patch.object(Bot.Hook, "trigger", new=AsyncMock(return_value=None)):
        assert await choice.ask_ai_choice(msg, ["apple", "banana"]) is None
    return True


async def _test_ask_ai_choice_success_with_petal():
    msg = _FakeMessageSession()
    hook_result = SimpleNamespace(status=choice.STATUS_OK, text="1. banana", petal=7, chain=[])
    trigger = AsyncMock(return_value=hook_result)
    with patch.object(Bot.Hook, "trigger", new=trigger):
        result = await choice.ask_ai_choice(msg, ["apple", "banana"])
    assert result is not None
    assert str(result[0]) == "banana"
    assert result[1].key == "petal.message.cost"
    assert result[1].kwargs == {"amount": 7}
    # 提示词按会话语言注入拒答语句
    assert _ZH_CN_REFUSAL in trigger.await_args.kwargs["args"]["instructions"]
    return True


async def _test_ask_ai_choice_refusal():
    msg = _FakeMessageSession()
    hook_result = SimpleNamespace(status=choice.STATUS_OK, text=_ZH_CN_REFUSAL, petal=0, chain=[])
    with patch.object(Bot.Hook, "trigger", new=AsyncMock(return_value=hook_result)):
        try:
            await choice.ask_ai_choice(msg, ["apple", "banana"])
        except SessionFinished:
            pass
        else:
            return False
    return len(msg.sent) == 1 and msg.sent[0].key == choice.REFUSAL_KEY


async def _test_ask_ai_choice_not_enough_petal():
    msg = _FakeMessageSession()
    hook_result = SimpleNamespace(status=choice.STATUS_NOT_ENOUGH_PETAL, text="", petal=0, chain=[])
    with patch.object(Bot.Hook, "trigger", new=AsyncMock(return_value=hook_result)):
        try:
            await choice.ask_ai_choice(msg, ["apple", "banana"])
        except SessionFinished:
            pass
        else:
            return False
    return len(msg.sent) == 1 and msg.sent[0].key == "petal.message.cost.not_enough"


async def _test_ask_ai_choice_unavailable_status():
    msg = _FakeMessageSession()
    hook_result = SimpleNamespace(status="unavailable", text="", petal=0, chain=[])
    with patch.object(Bot.Hook, "trigger", new=AsyncMock(return_value=hook_result)):
        assert await choice.ask_ai_choice(msg, ["apple", "banana"]) is None
    return True


@func_case
async def test_random_choice_ai(tester: Tester):
    """modules.random.choice: AI 选择流程与本地回退测试"""
    await tester.test(_test_build_choice_prompt, "候选元素提示词构造")
    await tester.test(_test_build_instructions_injects_localized_refusal, "提示词按会话语言注入拒答语句")
    await tester.test(_test_refusal_texts_come_from_locales, "拒答语句取自各语言本地化文件")
    await tester.test(_test_instructions_cover_randomness_and_brand_safety, "提示词覆盖任意挑选与品牌侮辱拦截")
    await tester.test(_test_match_choice, "模型输出还原为候选元素")
    await tester.test(_test_ask_ai_choice_fallback_without_hook, "ai 模块未加载时回退")
    await tester.test(_test_ask_ai_choice_fallback_when_not_executed, "hook 未被分发执行时回退")
    await tester.test(_test_ask_ai_choice_without_prompt_text, "提示词文件缺失时回退")
    await tester.test(_test_ask_ai_choice_fallback_on_hook_failure, "hook 调用失败时回退")
    await tester.test(_test_ask_ai_choice_success_with_petal, "选择成功并提示花瓣消耗")
    await tester.test(_test_ask_ai_choice_refusal, "模型规避输出时返回拒答文案")
    await tester.test(_test_ask_ai_choice_unmatched_reply, "模型输出候选以外的内容时拒答")
    await tester.test(_test_ask_ai_choice_not_enough_petal, "花瓣不足时提示且不回退")
    await tester.test(_test_ask_ai_choice_unavailable_status, "模型不可用时回退")
    return tester
