"""read_all_messages 特性与正则模块管控单元测试。

QQ 官方机器人在群主未开启「读取全部消息」权限时只收到提及自身的消息，此时正则模块的
触发会变得断续且难以解释，推送权限亦多半未开。平台不提供查询推送权限的接口，故以消息
事件类型为判据，一并关闭两类模块。
"""

from attr import evolve
from unittest.mock import patch

from bots.qqbot.features import group_disable_read_all_message_features
from core.builtins.parser.message import regex_module_enabled
from core.builtins.session.features import Features
from core.builtins.session.info import SessionInfo
from core.builtins.session.internal import MessageSession
from core.constants.exceptions import SessionFinished
from core.loader import ModulesManager
from core.logger import Logger
from core.tester import func_case, Tester
from core.types.module import Module
from modules.core.modules import UNSUPPORTED_PROMPTS, config_modules


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


def _test_feature_defaults_to_true():
    """未声明时应视作可读取全部消息，以免各平台都要显式声明。"""
    return Features().read_all_messages is True


def _test_feature_can_be_disabled():
    """平台可经 evolve 关闭该项，用于 QQ 官方机器人的提及消息场景。"""
    return evolve(Features(), read_all_messages=False).read_all_messages is False


def _test_session_info_declares_field():
    """SessionInfo 须声明同名字段，否则该项无法随会话序列化传至 server 进程。"""
    return "read_all_messages" in {x.name for x in SessionInfo.__attrs_attrs__}


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


def _test_module_regex_defaults_to_false():
    """未声明的模块不应被当作正则模块。"""
    return _make_module().regex is False


def _test_module_regex_can_be_set():
    """声明后该标记须落到 Module 上，并出现在 to_dict() 中。"""
    mod = _make_module(regex=True)
    return mod.regex is True and mod.to_dict()["regex"] is True


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


def _test_unsupported_reason_none():
    """无标记的模块在任何会话中都不受限。"""
    mod = _make_module()
    return mod.unsupported_reason(_FakeSession(support_rss=False, read_all_messages=False)) is None


def _test_unsupported_prompts_cover_all_reasons():
    """每种成因都须有对应文案，否则拒绝时无从提示。"""
    return set(UNSUPPORTED_PROMPTS) == {"rss", "regex"} and all(
        key.startswith("core.message.module.enable.unsupported_") for key in UNSUPPORTED_PROMPTS.values()
    )


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


def _test_qqbot_override_closes_both():
    """提及消息场景须同时关闭推送与全部消息读取，且不改动其余能力。

    该场景不豁免模块启用检查（require_enable_modules 保持默认的 True），命令路径因而
    照常要求模块已启用。被拒绝启用的正则模块，其命令在此场景中一并不可用，此为有意为之。
    """
    override = group_disable_read_all_message_features
    return (
        override.support_rss is False
        and override.read_all_messages is False
        and override.require_enable_modules is True
        and override.support_image is True
    )


def _test_regex_modules_are_marked():
    """注册了正则处理函数的模块须带 regex 标记，base 模块除外。"""
    unmarked = [
        name for name, mod in ModulesManager.modules.items() if mod.regex_list.set and not mod.regex and not mod.base
    ]
    return unmarked == []


async def _enable_prompt(module_name: str) -> str:
    """在 QQ 官方机器人的提及消息场景中跑一遍启用流程，取回渲染后的提示。

    该场景的会话特性直接取自 bots/qqbot/features.py，故本用例同时守住了那份声明。

    :param module_name: 待启用的模块名。
    :return: 提示文案，多条以竖线相接。
    """
    session_info = await SessionInfo.assign(
        target_id=f"TEST|Group|enable_{module_name}",
        target_from="TEST|Group",
        client_name="TEST",
        sender_id="TEST|1",
        features=group_disable_read_all_message_features,
    )
    msg = MessageSession(session_info=session_info)
    msg.parsed_msg = {"enable": True, "<module>": module_name, "...": []}
    captured = []

    async def _capture(self, message_chain=None, **kwargs):
        captured.append(message_chain)
        raise SessionFinished

    with (
        patch.object(MessageSession, "finish", new=_capture),
        patch.object(MessageSession, "send_message", new=_capture),
        patch.object(MessageSession, "check_super_user", lambda self: False),
    ):
        try:
            await config_modules(msg)
        except SessionFinished:
            pass

    rendered = []
    for chain in captured:
        for element in chain if isinstance(chain, list) else [chain]:
            rendered.append(session_info.locale.t_str(str(element)))
    return " | ".join(rendered)


async def _test_enable_regex_module_is_rejected():
    """受限场景中启用正则模块应给出指向权限的提示。"""
    expected = "失败：此场景不支持正则模块，请检查是否开启对应的权限。"
    actual = await _enable_prompt("wiki_inline")
    if actual != expected:
        Logger.error(f"Expected regex rejection prompt {expected!r}, got {actual!r}")
        return False
    return True


async def _test_enable_rss_module_is_rejected():
    """受限场景中启用推送模块应给出指向权限的提示。"""
    expected = "失败：此场景不支持推送模块，请检查是否开启对应的权限。"
    actual = await _enable_prompt("minecraft_news")
    if actual != expected:
        Logger.error(f"Expected RSS rejection prompt {expected!r}, got {actual!r}")
        return False
    return True


async def _test_enable_plain_module_still_works():
    """未受标记的模块在同一场景中照常启用，确认拦截未误伤。"""
    return "成功" in await _enable_prompt("coin")


@func_case
async def test_read_all_messages(tester: Tester):
    """core: read_all_messages 特性与正则模块管控"""
    await tester.test(_test_feature_defaults_to_true, "特性默认为真")
    await tester.test(_test_feature_can_be_disabled, "特性可被关闭")
    await tester.test(_test_session_info_declares_field, "SessionInfo 声明该字段")
    await tester.test(_test_feature_injects_into_session, "特性可注入会话")
    await tester.test(_test_module_regex_defaults_to_false, "模块 regex 标记默认为假")
    await tester.test(_test_module_regex_can_be_set, "模块 regex 标记可置真")
    await tester.test(_test_unsupported_reason_rss, "推送模块受限判定")
    await tester.test(_test_unsupported_reason_regex, "正则模块受限判定")
    await tester.test(_test_unsupported_reason_none, "无标记模块不受限")
    await tester.test(_test_unsupported_prompts_cover_all_reasons, "受限成因均有文案")
    await tester.test(_test_regex_blocked_when_cannot_read_all, "无权限时正则不参与匹配")
    await tester.test(_test_regex_allowed_when_can_read_all, "有权限时正则照常匹配")
    await tester.test(_test_base_module_still_exempt, "base 模块仍豁免")
    await tester.test(_test_non_regex_module_unaffected, "未标记模块不受影响")
    await tester.test(_test_qqbot_override_closes_both, "QQBot 覆盖关闭两项")
    await tester.test(_test_regex_modules_are_marked, "正则模块均已标记")
    await tester.test(_test_enable_regex_module_is_rejected, "启用正则模块被拒")
    await tester.test(_test_enable_rss_module_is_rejected, "启用推送模块被拒")
    await tester.test(_test_enable_plain_module_still_works, "普通模块照常启用")
    return tester
