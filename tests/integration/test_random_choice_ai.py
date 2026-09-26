"""random choice 接入 ai.ask 的集成测试。"""

from contextlib import ExitStack
from unittest.mock import AsyncMock, patch

from core.builtins.message.internal import Plain
from core.tester import func_case, Tester, Predicate
from modules.ai import hook

_CANDIDATES = ("apple", "banana", "cherry")


def _patch_llm(models: list[dict], default: str | None = None):
    """固定 ai 模块可见的模型列表，避免依赖开发者本机的 llm_api_list.yaml。"""
    stack = ExitStack()
    stack.enter_context(patch.object(hook, "llm_api_list", models))
    stack.enter_context(patch.object(hook, "llm_list", [model["name"] for model in models]))
    stack.enter_context(patch.object(hook, "llm_su_list", []))
    stack.enter_context(patch.object(hook, "default_llm", default))
    return stack


def _output_text(result) -> str:
    output = result.get("output")
    return "" if not output else "".join(str(item) for item in output)


@func_case
async def test_random_choice_ai(tester: Tester):
    """random choice 通过 ai.ask 完成选择"""
    ask_llm = AsyncMock(return_value=([Plain("banana")], 10, 20, 0, 0, []))
    models = [{"name": "alpha", "model_name": "m", "api_url": "http://127.0.0.1", "api_key": "k"}]

    def is_ai_reply(result):
        return ask_llm.await_count == 1 and "banana" in _output_text(result)

    with _patch_llm(models, "alpha"), patch("modules.ai.llm.ask_llm", ask_llm):
        await tester.integrate("~random choice apple banana cherry", Predicate(is_ai_reply), "应输出模型选择的元素")

    return tester


@func_case
async def test_random_choice_ai_before_dirty_check(tester: Tester):
    """AI 选择先于本地 dirty_words 检查输出"""
    ask_llm = AsyncMock(return_value=([Plain("banana")], 10, 20, 0, 0, []))
    models = [{"name": "alpha", "model_name": "m", "api_url": "http://127.0.0.1", "api_key": "k"}]

    def is_ai_reply(result):
        return ask_llm.await_count == 1 and "banana" in _output_text(result)

    with (
        _patch_llm(models, "alpha"),
        patch("modules.ai.llm.ask_llm", ask_llm),
        # 本地检查判定不合规也不应拦截 AI 结果，内容审核由 ai 模块负责
        patch("modules.random.check_bool", AsyncMock(return_value=True)),
    ):
        await tester.integrate("~random choice apple banana cherry", Predicate(is_ai_reply), "AI 结果先于本地检查输出")

    return tester


@func_case
async def test_random_choice_fallback_dirty_check(tester: Tester):
    """ai 模块不可用时回退到本地实现并执行 dirty_words 检查"""

    def is_refusal(result):
        text = _output_text(result).strip()
        return bool(text) and not any(candidate in text for candidate in _CANDIDATES)

    with _patch_llm([]), patch("modules.random.check_bool", AsyncMock(return_value=True)):
        await tester.integrate(
            "~random choice apple banana cherry", Predicate(is_refusal), "回退路径命中 dirty_words 时拒答"
        )

    return tester
