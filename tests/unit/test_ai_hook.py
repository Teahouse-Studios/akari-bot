"""modules.ai.hook ai.ask 具名 hook 单元测试。"""

from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from core.builtins.bot import Bot
from core.builtins.hooks import dispatch_module_hook_outcome
from core.builtins.message.internal import Plain
from core.tester import func_case, Tester
from modules.ai import hook


def _patch_llm(models: list[dict], default: str | None):
    stack = ExitStack()
    stack.enter_context(patch.object(hook, "llm_api_list", models))
    stack.enter_context(patch.object(hook, "llm_list", [model["name"] for model in models]))
    stack.enter_context(patch.object(hook, "llm_su_list", []))
    stack.enter_context(patch.object(hook, "default_llm", default))
    return stack


def _session_info(target_default_llm: str | None = None, superuser: bool = False):
    target_union_info = (
        SimpleNamespace(target_data={"ai_default_llm": target_default_llm}) if target_default_llm else None
    )
    return SimpleNamespace(superuser=superuser, target_union_info=target_union_info)


async def _test_ask_ai_without_session():
    ctx = Bot.ModuleHookContext({"prompt": "hi"}, session_info=None)
    result = await hook.ask_ai(ctx)
    assert result.status == hook.STATUS_UNAVAILABLE
    assert not result.chain
    return True


async def _test_ask_ai_without_available_llm():
    ctx = Bot.ModuleHookContext({"prompt": "hi"}, session_info=_session_info())
    with _patch_llm([], None):
        result = await hook.ask_ai(ctx)
    assert result.status == hook.STATUS_UNAVAILABLE
    return True


def _test_resolve_llm_priority():
    models = [{"name": "alpha"}, {"name": "beta"}]
    with _patch_llm(models, "alpha"):
        # 调用方指定 > 场景默认 > 模块默认
        assert hook.resolve_llm("ALPHA", _session_info("beta"))["name"] == "alpha"
        assert hook.resolve_llm(None, _session_info("beta"))["name"] == "beta"
        assert hook.resolve_llm(None, _session_info())["name"] == "alpha"
        # 显式指定的模型不可用时不替换，场景默认模型离线时回落模块默认
        assert hook.resolve_llm("gamma", _session_info("beta")) is None
        assert hook.resolve_llm(None, _session_info("gamma"))["name"] == "alpha"
    return True


async def _test_ask_ai_not_enough_petal():
    models = [{"name": "alpha", "model_name": "m", "api_url": "u", "api_key": "k"}]
    ctx = Bot.ModuleHookContext({"prompt": "hi"}, session_info=_session_info())
    with (
        _patch_llm(models, "alpha"),
        patch.object(hook, "precount_petal", lambda *args, **kwargs: False),
    ):
        result = await hook.ask_ai(ctx)
    assert result.status == hook.STATUS_NOT_ENOUGH_PETAL
    assert result.petal == 0
    return True


async def _test_ask_ai_success():
    models = [{"name": "alpha", "model_name": "m", "api_url": "u", "api_key": "k"}]
    ctx = Bot.ModuleHookContext(
        {"prompt": "hi", "instructions": "只输出一个元素", "use_tools": False},
        session_info=_session_info(),
    )
    ask_llm = AsyncMock(return_value=([Plain("banana")], 10, 20, 0, 0, []))
    with (
        _patch_llm(models, "alpha"),
        patch("modules.ai.llm.ask_llm", ask_llm),
        patch.object(hook, "count_token_petal", AsyncMock(return_value=3)),
    ):
        result = await hook.ask_ai(ctx)
    assert result.status == hook.STATUS_OK
    assert result.text == "banana"
    assert result.petal == 3
    assert result.llm == "alpha"
    assert ask_llm.await_args.kwargs["extra_instructions"] == "只输出一个元素"
    assert ask_llm.await_args.kwargs["use_tools"] is False
    return True


async def _test_ask_ai_dispatch():
    outcome = await dispatch_module_hook_outcome("ai.ask", args={"prompt": "hi"})
    assert outcome.executed == 1
    assert outcome.failed == 0
    assert outcome.result.status == hook.STATUS_UNAVAILABLE
    return True


@func_case
async def test_ai_hook(tester: Tester):
    """modules.ai.hook: ai.ask 调用契约测试"""
    await tester.test(_test_ask_ai_without_session, "缺少会话信息时不可用")
    await tester.test(_test_ask_ai_without_available_llm, "无可用模型时不可用")
    await tester.test(_test_resolve_llm_priority, "模型选择优先级")
    await tester.test(_test_ask_ai_not_enough_petal, "花瓣不足时返回对应状态")
    await tester.test(_test_ask_ai_success, "调用成功时回传回答与花瓣扣除数")
    await tester.test(_test_ask_ai_dispatch, "具名 hook 可被分发执行")
    return tester
