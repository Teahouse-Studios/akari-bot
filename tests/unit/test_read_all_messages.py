"""read_all_messages 特性与正则模块管控单元测试。

QQ 官方机器人在群主未开启「读取全部消息」权限时只收到提及自身的消息，此时正则模块的
触发会变得断续且难以解释，推送权限亦多半未开。平台不提供查询推送权限的接口，故以消息
事件类型为判据，一并关闭两类模块。
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from bots.qqbot.features import group_disable_read_all_message_features
from core.builtins.parser.message import regex_module_enabled
from core.builtins.session.features import Features
from core.builtins.session.info import SessionInfo
from core.builtins.session.internal import MessageSession
from core.builtins.session.bot_state import BotState
from core.constants.exceptions import SessionFinished
from core.logger import Logger
from core.tester import func_case, Tester
from core.types.module import Module
from modules.core.common_tools.help import create_module_entry, format_module_entries
from modules.core.admin_tools.modules import config_modules


def _make_module(**kwargs) -> Module:
    """构造一个用于判定的最简模块。

    :param kwargs: 覆盖到 Module.assign 上的字段。
    """
    base = {
        "module_name": "unittest_module",
        "alias": None,
        "recommend_modules": None,
        "developers": None,
    }
    base.update(kwargs)
    return Module.assign(**base)


async def _test_feature_injects_into_session():
    """特性须能注入会话。

    inject_features() 以 asdict(features) 逐字段 setattr，SessionInfo 若缺少同名字段
    会在注入时抛错。此处取 False 而非默认的 True，默认值相同时测不出遗漏。
    """
    session_info = await SessionInfo.assign(
        target_id="TEST|Group|read_all_messages",
        target_from="TEST|Group",
        client_name="TEST",
        sender_id="TEST|1",
        features=Features(read_all_messages=False),
    )
    return session_info.read_all_messages is False


class _FakeSession:
    """仅承载判定所需两项标志的最简会话替身。"""

    def __init__(self, support_rss: bool = True, read_all_messages: bool = True):
        self.support_rss = support_rss
        self.read_all_messages = read_all_messages


def _test_unsupported_reason_rss():
    """推送模块在不支持推送的会话中受限。"""
    mod = _make_module(rss=True)
    return (
        mod.unsupported_reason(_FakeSession(support_rss=False)) == "rss"
        and mod.unsupported_reason(_FakeSession()) is None
    )


def _test_unsupported_reason_regex():
    """正则模块在读不到全部消息的会话中受限。"""
    mod = _make_module(regex=True)
    return (
        mod.unsupported_reason(_FakeSession(read_all_messages=False)) == "regex"
        and mod.unsupported_reason(_FakeSession()) is None
    )


def _test_unsupported_reason_event():
    """事件模块在读不到全部消息的场景中受限。"""
    mod = _make_module(event=True)
    return (
        mod.unsupported_reason(_FakeSession(read_all_messages=False)) == "event"
        and mod.unsupported_reason(_FakeSession()) is None
    )


def _test_unsupported_reason_none():
    """无标记的模块在任何会话中都不受限。"""
    mod = _make_module()
    return mod.unsupported_reason(_FakeSession(support_rss=False, read_all_messages=False)) is None


def _test_event_module_markdown_strikethrough():
    """Markdown 模块菜单须用删除线标出当前无法开启的事件模块。"""
    entry = create_module_entry(_make_module(event=True), "captcha", [], _FakeSession(read_all_messages=False))
    return format_module_entries([entry]) == "🔐 ~~captcha~~"


def _test_regex_blocked_when_cannot_read_all():
    """读不到全部消息时，正则模块即便已启用也不应参与匹配。"""
    mod = _make_module(regex=True)
    return regex_module_enabled(mod, "unittest_module", ["unittest_module"], False) is False


def _test_regex_allowed_when_can_read_all():
    """可读取全部消息时，已启用的正则模块照常参与匹配。"""
    mod = _make_module(regex=True)
    return regex_module_enabled(mod, "unittest_module", ["unittest_module"], True) is True


def _test_base_module_still_exempt():
    """base 模块无须启用即可生效，该豁免不因权限而改变。"""
    mod = _make_module(regex=True, base=True)
    return regex_module_enabled(mod, "unittest_module", [], False) is True


def _test_non_regex_module_unaffected():
    """未标记的模块不受该权限影响，仍只看启用状态。"""
    mod = _make_module()
    return (
        regex_module_enabled(mod, "unittest_module", ["unittest_module"], False) is True
        and regex_module_enabled(mod, "unittest_module", [], False) is False
    )


async def _enable_prompt(
    module_name: str,
    features=group_disable_read_all_message_features,
    target_from: str = "TEST|Group",
    client_name: str = "TEST",
    bot_state: BotState | None = None,
    return_session_info: bool = False,
    target_suffix: str = "",
) -> str | tuple[str, SessionInfo]:
    """在 QQ 官方机器人的提及消息场景中跑一遍启用流程，取回渲染后的提示。

    该场景的会话特性直接取自 bots/qqbot/features.py，故本用例同时守住了那份声明。

    :param module_name: 待启用的模块名。
    :return: 提示文案，多条以竖线相接。
    """
    session_info = await SessionInfo.assign(
        target_id=f"{target_from}|enable_{module_name}{target_suffix}",
        target_from=target_from,
        client_name=client_name,
        sender_id=f"{client_name}|1",
        features=features,
    )
    msg = MessageSession(session_info=session_info)
    msg.parsed_msg = {"enable": True, "<module>": module_name, "...": []}
    captured = []

    async def _capture(self, message_chain=None, **kwargs):
        captured.append(message_chain)
        raise SessionFinished

    async def _check_bot_state(self):
        return bot_state

    with (
        patch.object(MessageSession, "finish", new=_capture),
        patch.object(MessageSession, "send_message", new=_capture),
        patch.object(MessageSession, "check_super_user", lambda self: False),
        patch.object(MessageSession, "check_bot_state", new=_check_bot_state),
    ):
        try:
            await config_modules(msg)
        except SessionFinished:
            pass

    rendered = []
    for chain in captured:
        for element in chain if isinstance(chain, list) else [chain]:
            rendered.append(session_info.locale.t_str(str(element)))
    output = " | ".join(rendered)
    return (output, session_info) if return_session_info else output


async def _test_enable_regex_module_is_rejected():
    """受限场景中启用正则模块应给出指向权限的提示。"""
    expected = "失败：此场景不支持正则模块，请检查是否开启对应的权限。"
    actual = await _enable_prompt("wiki-inline")
    if actual != expected:
        Logger.error(f"Expected regex rejection prompt {expected!r}, got {actual!r}")
        return False
    return True


async def _test_enable_rss_module_is_rejected():
    """受限场景中启用推送模块应给出指向权限的提示。"""
    expected = "失败：此场景不支持推送模块，请检查是否开启对应的权限。"
    actual = await _enable_prompt("minecraft-news")
    if actual != expected:
        Logger.error(f"Expected RSS rejection prompt {expected!r}, got {actual!r}")
        return False
    return True


async def _test_enable_plain_module_still_works():
    """未受标记的模块在同一场景中照常启用，确认拦截未误伤。"""
    return "成功" in await _enable_prompt("coin")


async def _test_enable_event_module_is_rejected():
    """读不到全部消息时事件模块应被拒绝开启。"""
    expected = "失败：此场景无法读取全部消息，不能开启事件模块，请先授予机器人对应权限。"
    actual = await _enable_prompt("captcha", target_from="QQBot|Group", client_name="QQBot")
    if actual != expected:
        Logger.error(f"Expected event rejection prompt {expected!r}, got {actual!r}")
        return False
    return True


async def _test_enable_event_module_warns_permissions():
    """成功开启事件模块后须提醒管理员授予事件与管理权限。"""
    actual = await _enable_prompt(
        "captcha",
        features=Features(read_all_messages=True),
        target_from="QQBot|Group",
        client_name="QQBot",
    )
    return "成功：开启模块“captcha”" in actual and "事件模块依赖平台事件订阅" in actual


async def _test_enable_captcha_is_rejected_when_bot_permissions_are_missing():
    """BotState 明确缺少 captcha 所需权限时不得记录模块启用状态。"""
    actual, session_info = await _enable_prompt(
        "captcha",
        features=Features(read_all_messages=True),
        target_from="QQBot|Group",
        client_name="QQBot",
        bot_state=BotState(
            can_read_all_messages=True,
            can_send_messages=True,
            can_send_proactive_messages=False,
            can_manage_members=False,
            can_restrict_members=False,
        ),
        return_session_info=True,
        target_suffix="_missing_bot_permissions",
    )
    return (
        "缺少开启模块所需的平台权限" in actual
        and "主动发送消息" in actual
        and "管理成员" in actual
        and "限制成员" in actual
        and "成功：开启模块“captcha”" not in actual
        and "captcha" not in (session_info.target_union_info.modules or [])
    )


async def _test_enable_captcha_allows_unknown_bot_permissions():
    """平台未提供状态字段时保持兼容，不应因 None 误拒绝模块。"""
    actual = await _enable_prompt(
        "captcha",
        features=Features(read_all_messages=True),
        target_from="QQBot|Group",
        client_name="QQBot",
        bot_state=BotState(can_read_all_messages=True),
        target_suffix="_unknown_bot_permissions",
    )
    return "成功：开启模块“captcha”" in actual


async def _test_enable_all_skips_modules_with_missing_bot_permissions():
    """enable all 只写入已满足机器人权限要求的模块。"""
    allowed = _make_module(module_name="allowed", required_bot_permissions=["can_send_messages"])
    blocked = _make_module(module_name="blocked", required_bot_permissions=["can_manage_members"])
    allowed._db_load = blocked._db_load = True
    config_module = AsyncMock(return_value=True)
    session_info = SessionInfo(
        target_id="TEST|Group|enable-all-bot-permissions",
        target_from="TEST|Group",
        client_name="TEST",
        enabled_modules=[],
        target_union_info=SimpleNamespace(config_module=config_module),
    )
    msg = MessageSession(session_info=session_info)
    msg.parsed_msg = {"enable": True, "all": True, "<module>": None, "...": []}

    async def _finish(_self, _message_chain=None, **_kwargs):
        raise SessionFinished

    async def _check_bot_state(_self):
        return BotState(can_send_messages=True, can_manage_members=False)

    with (
        patch(
            "modules.core.admin_tools.modules.ModulesManager.return_modules_list",
            return_value={"allowed": allowed, "blocked": blocked},
        ),
        patch.object(MessageSession, "finish", new=_finish),
        patch.object(MessageSession, "check_super_user", lambda self: False),
        patch.object(MessageSession, "check_bot_state", new=_check_bot_state),
    ):
        try:
            await config_modules(msg)
        except SessionFinished:
            pass
    return config_module.await_args.args == (["allowed"], True)


@func_case
async def test_read_all_messages(tester: Tester):
    """core: read_all_messages 特性与正则模块管控"""
    await tester.test(_test_feature_injects_into_session, "特性可注入会话")
    await tester.test(_test_unsupported_reason_rss, "推送模块受限判定")
    await tester.test(_test_unsupported_reason_regex, "正则模块受限判定")
    await tester.test(_test_unsupported_reason_event, "事件模块受限判定")
    await tester.test(_test_unsupported_reason_none, "无标记模块不受限")
    await tester.test(_test_event_module_markdown_strikethrough, "事件模块菜单删除线")
    await tester.test(_test_regex_blocked_when_cannot_read_all, "无权限时正则不参与匹配")
    await tester.test(_test_regex_allowed_when_can_read_all, "有权限时正则照常匹配")
    await tester.test(_test_base_module_still_exempt, "base 模块仍豁免")
    await tester.test(_test_non_regex_module_unaffected, "未标记模块不受影响")
    await tester.test(_test_enable_regex_module_is_rejected, "启用正则模块被拒")
    await tester.test(_test_enable_rss_module_is_rejected, "启用推送模块被拒")
    await tester.test(_test_enable_event_module_is_rejected, "启用事件模块被拒")
    await tester.test(_test_enable_event_module_warns_permissions, "事件模块权限提醒")
    await tester.test(
        _test_enable_captcha_is_rejected_when_bot_permissions_are_missing, "Captcha 缺少机器人权限时拒绝启用"
    )
    await tester.test(_test_enable_captcha_allows_unknown_bot_permissions, "未知机器人权限不误拒绝 Captcha")
    await tester.test(_test_enable_all_skips_modules_with_missing_bot_permissions, "批量启用跳过缺少机器人权限的模块")
    await tester.test(_test_enable_plain_module_still_works, "普通模块照常启用")
    return tester
