"""module reload 对基础模块的处理测试。"""

from unittest.mock import AsyncMock, patch

from core.builtins.session.info import SessionInfo
from core.builtins.session.internal import MessageSession
from core.constants.exceptions import SessionFinished
from core.tester import Tester, func_case
from core.types.module import Module
from modules.core.admin_tools.modules import config_modules


def _make_module(name, *, base=False):
    module = Module.assign(module_name=name, alias=None, recommend_modules=None, developers=None, base=base)
    module._db_load = True
    return module


async def _run_reload(module_name, *, base=False, related=(), confirm=True):
    session_info = SessionInfo(
        target_id=f"TEST|Group|reload_{module_name}",
        target_from="TEST|Group",
        client_name="TEST",
        sender_id="TEST|1",
        enabled_modules=[],
    )
    msg = MessageSession(session_info=session_info)
    msg.parsed_msg = {"reload": True, "<module>": module_name, "...": []}
    captured = []
    confirms = []
    reload_mock = AsyncMock(return_value=(True, 1))

    async def _capture(self, message_chain=None, **_kwargs):
        captured.append(message_chain)
        raise SessionFinished

    async def _confirm(self, message_chain=None, **_kwargs):
        confirms.append(message_chain)
        return confirm

    module = _make_module(module_name, base=base)
    with (
        patch.object(MessageSession, "finish", new=_capture),
        patch.object(MessageSession, "send_message", new=_capture),
        patch.object(MessageSession, "wait_confirm", new=_confirm),
        patch.object(MessageSession, "check_super_user", lambda self: True),
        patch(
            "modules.core.admin_tools.modules.ModulesManager.return_modules_list",
            return_value={module_name: module},
        ),
        patch(
            "modules.core.admin_tools.modules.ModulesManager.search_related_module",
            return_value=list(related),
        ),
        patch("modules.core.admin_tools.modules.ModulesManager.reload_module", new=reload_mock),
    ):
        try:
            await config_modules(msg)
        except SessionFinished:
            pass

    def _render(chains):
        rendered = []
        for chain in chains:
            if chain is None:
                continue
            for element in chain if isinstance(chain, list) else [chain]:
                rendered.append(session_info.locale.t_str(str(element)))
        return " | ".join(rendered)

    return _render(captured), _render(confirms), reload_mock


async def _test_base_module_reload_is_not_blocked():
    output, confirms, reload_mock = await _run_reload("unit_base", base=True)
    return (
        reload_mock.await_args.args == ("unit_base",)
        and reload_mock.await_count == 1
        and not confirms
        and "成功重载模块" in output
        and "此操作已被阻止" not in output
    )


async def _test_base_module_reload_keeps_related_confirmation():
    output, confirms, reload_mock = await _run_reload("unit_base", base=True, related=["unit_related"])
    return (
        reload_mock.await_count == 1
        and "该操作将额外重载以下模块" in confirms
        and "unit_related" in confirms
        and "成功重载模块" in output
    )


async def _test_rejected_related_confirmation_skips_reload():
    output, confirms, reload_mock = await _run_reload("unit_base", base=True, related=["unit_related"], confirm=False)
    return reload_mock.await_count == 0 and not output and "该操作将额外重载以下模块" in confirms


@func_case
async def test_module_reload(tester: Tester):
    """modules.core.admin_tools.modules: module reload 基础模块处理测试"""
    await tester.test(_test_base_module_reload_is_not_blocked, "基础模块重载不再被拦截测试")
    await tester.test(_test_base_module_reload_keeps_related_confirmation, "基础模块重载保留联动模块确认测试")
    await tester.test(_test_rejected_related_confirmation_skips_reload, "拒绝联动确认时不执行重载测试")
    return tester
