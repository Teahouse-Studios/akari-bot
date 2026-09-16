"""生产命令模板解析失败后的恢复与提示边界。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from core.builtins.message.chain import MessageChain
from core.builtins.parser.args import parse_template
from core.builtins.parser.hooks import Handled, HookPoint, ParserHookExecutor, RecoveryProposal, build_subscription
from core.builtins.parser.message import _execute_module
from core.constants.exceptions import InvalidCommandFormatError
from core.i18n import Locale
from core.loader import ModulesManager
from core.tester import Tester, func_case
from core.types import Module
from core.types.module.component_meta import CommandMeta, HookMeta


async def _run_template_recovery(
    *, result=None, confirmed=True, suppress=False, allow_recovery=True, matched=False, execution_error=False
):
    module_name = "__template_recovery"
    called = []
    unmatched = []

    async def command(msg):
        called.append(msg.trigger_msg)
        if execution_error:
            raise InvalidCommandFormatError

    async def on_unmatched(ctx):
        unmatched.append((ctx.command_first_word, ctx.data["unmatched_kind"]))
        return result

    module = Module.assign(module_name=module_name, alias=None, recommend_modules=None, developers=None, base=True)
    module._db_load = True
    module.suppress_invalid_prompt = suppress
    module.command_list.add(CommandMeta(function=command, command_template=parse_template(["run"])))
    meta = HookMeta(function=on_unmatched, point=HookPoint.COMMAND_UNMATCHED, server_scope=True)
    builtin_policies = ModulesManager.modules.get("parser_policies")
    modules = {module_name: module}
    subscriptions = [build_subscription(module_name, meta, 0)]
    if builtin_policies is not None:
        modules["parser_policies"] = builtin_policies
        subscriptions.extend(ModulesManager.parser_hook_subscriptions.get(HookPoint.COMMAND_UNMATCHED, ()))
    manager = SimpleNamespace(
        modules=modules,
        parser_hook_subscriptions={HookPoint.COMMAND_UNMATCHED: subscriptions},
    )
    executor = ParserHookExecutor(manager)
    session = SimpleNamespace(
        target_from="TEST",
        client_name="TEST",
        target_id="TEST|recovery",
        sender_id="TEST|recovery-user",
        target_union_id=None,
        sender_union_id=None,
        tmp={},
        prefixes=["~"],
        messages=None,
        bot_name="Bot",
        muted=False,
        locale=Locale("zh_cn"),
        enabled_modules=[],
        require_enable_modules=False,
        typing_prompt_enabled=False,
        invalid_module_prompt_enabled=True,
        refresh_info=AsyncMock(),
    )
    msg = SimpleNamespace(
        session_info=session,
        trigger_msg=f"{module_name} {'run' if matched else 'rnu'}",
        parsed_msg={},
        sent=[],
        send_message=AsyncMock(),
        wait_confirm=AsyncMock(return_value=confirmed),
        check_super_user=lambda: False,
    )
    with (
        patch("core.builtins.parser.message.ExecutionLockList.remove"),
        patch("core.builtins.parser.message.has_hook_subscribers", side_effect=executor.has_subscribers),
        patch("core.builtins.parser.message.dispatch_parser_hook", side_effect=executor.dispatch),
        patch("core.builtins.parser.message.ModulesManager.return_modules_list", return_value={module_name: module}),
    ):
        await _execute_module(msg, manager.modules, module_name, "[recovery test]", allow_recovery=allow_recovery)
    return msg, called, unmatched


async def _test_template_recovery_executes_after_confirmation():
    proposal = RecoveryProposal("__template_recovery run", "__template_recovery")
    msg, called, unmatched = await _run_template_recovery(result=proposal)
    assert unmatched == [("__template_recovery", "template")]
    assert called == [proposal.trigger_msg]
    assert msg.wait_confirm.await_count == 1
    assert msg.session_info.refresh_info.await_count == 1
    assert msg.send_message.await_count == 0
    return True


async def _test_template_recovery_prompt_boundaries():
    for options, expected_unmatched, expected_prompt in (
        ({}, True, True),
        ({"allow_recovery": False}, True, True),
        ({"suppress": True}, False, False),
        ({"suppress": True, "allow_recovery": False}, False, False),
        ({"result": Handled()}, True, False),
        (
            {"result": RecoveryProposal("__template_recovery run", "__template_recovery"), "confirmed": False},
            True,
            False,
        ),
    ):
        msg, called, unmatched = await _run_template_recovery(**options)
        assert not called
        assert bool(unmatched) == expected_unmatched
        assert msg.send_message.await_count == int(expected_prompt)
        if expected_prompt:
            message = MessageChain.assign(msg.send_message.await_args.args[0])
            assert [element.key for element in message] == ["parser.command.invalid.syntax"]
    return True


async def _test_execution_format_error_does_not_retry():
    msg, called, unmatched = await _run_template_recovery(matched=True, execution_error=True)
    assert called == ["__template_recovery run"]
    assert unmatched == [("__template_recovery", "syntax")]
    assert msg.send_message.await_count == 1
    assert msg.wait_confirm.await_count == 0
    return True


@func_case
async def test_parser_recovery(tester: Tester):
    await tester.test(_test_template_recovery_executes_after_confirmation, "模板未匹配经 hook 确认后执行")
    await tester.test(_test_template_recovery_prompt_boundaries, "模板恢复与静默、拒绝、默认提示边界")
    await tester.test(_test_execution_format_error_does_not_retry, "已执行命令的格式错误不进入恢复重试")
    return tester
