"""用户级 markdown 消息开关的单元测试。

QQ 官方机器人的 markdown 消息承载了行内指令操作、底部按钮与内嵌图片，此前只能由
配置项 qq_use_markdown 全局开关。本开关把这一选择下放到用户，经特性覆盖生效：
关闭后该用户的会话不再具备 markdown 相关能力，发送路径亦改走纯文本。

最易写错的一处是 support_markdown_toggle 自身——它必须在覆盖后仍为真，否则设置面板中
的该行会一并消失，用户再无入口把它开回来。
"""

from unittest.mock import patch

from attr import evolve
from botpy.message import GroupMessage

import bots.qqbot.context as qqbot_context
import bots.qqbot.features as qqbot_features_module
from bots.qqbot.config import QQBotConfig
from bots.qqbot.context import QQBotContextManager
from bots.qqbot.features import features as qqbot_features
from bots.qqbot.features import group_disable_read_all_message_features, resolve_features
from bots.qqbot.info import target_group_prefix
from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import ActionText, Plain
from core.builtins.session.features import Features
from core.builtins.session.info import SessionInfo
from core.database.models import SenderUnionInfo, TargetUnionInfo
from core.logger import Logger
from core.tester import func_case, Tester

# 用户数据中承载该偏好的键
SWITCH_KEY = "use_markdown"

# 平台能力集在导入时即依配置定型，qq_use_markdown 为假的部署上，markdown 相关能力全为假，
# 覆盖也就无从谈起。故各用例另建一份「markdown 已开启」的基准并打桩该开关，
# 使断言只考察覆盖逻辑本身，不受本地配置左右。
MARKDOWN_ON_BASE = evolve(
    qqbot_features,
    support_markdown=True,
    support_markdown_table=True,
    support_action_text=True,
    support_button=True,
    support_markdown_toggle=True,
    use_url_md_format=True,
)


def _resolve(sender_data: dict | None, base: Features = MARKDOWN_ON_BASE) -> Features:
    """在「全局 markdown 已开启」的前提下解析能力。

    :param sender_data: 用户数据；传 None 表示该会话没有用户 union。
    :param base: 覆盖所基于的能力集。
    :return: 解析后的能力集。
    """
    with patch.object(qqbot_features_module, "qq_use_markdown", True):
        return resolve_features(_make_session(sender_data), base)


def _make_session(sender_data: dict | None) -> SessionInfo:
    """构造一个带用户数据的会话。

    :param sender_data: 用户数据；传 None 表示该会话没有用户 union（如主动推送）。
    :return: 会话信息。
    """
    return SessionInfo(
        target_id="QQBot|Group|markdown_toggle",
        sender_id="QQBot|1",
        target_from="QQBot|Group",
        client_name="QQBot",
        session_id="markdown-toggle",
        target_union_info=TargetUnionInfo(union_id="UTID|1", target_data={}),
        sender_union_info=(
            None if sender_data is None else SenderUnionInfo(union_id="USID|1", sender_data=sender_data)
        ),
    )


def _test_feature_defaults_to_false() -> bool:
    """该能力是少数平台才有的，默认不具备"""
    if Features().support_markdown_toggle is not False:
        Logger.error("support_markdown_toggle should default to False")
        return False
    return True


def _test_session_info_declares_field() -> bool:
    """SessionInfo 须声明同名字段，否则该项无法随会话序列化传至 server 进程"""
    if "support_markdown_toggle" not in {x.name for x in SessionInfo.__attrs_attrs__}:
        Logger.error("SessionInfo must declare support_markdown_toggle for it to survive serialisation")
        return False
    return True


async def _test_feature_injects_into_session() -> bool:
    """特性须能注入会话。此处取 True 而非默认的 False，默认值相同时测不出遗漏"""
    session_info = await SessionInfo.assign(
        target_id="TEST|Group|markdown_toggle",
        target_from="TEST|Group",
        client_name="TEST",
        sender_id="TEST|1",
        features=Features(support_markdown_toggle=True),
    )
    if session_info.support_markdown_toggle is not True:
        Logger.error("support_markdown_toggle should be injectable into a session")
        return False
    return True


def _test_qqbot_follows_markdown_config() -> bool:
    """QQBot 的该能力须跟随 qq_use_markdown：全局关掉 markdown 时这个开关也无从谈起"""
    if qqbot_features.support_markdown_toggle is not QQBotConfig.qq_use_markdown:
        Logger.error("QQBot should tie support_markdown_toggle to qq_use_markdown")
        return False
    return True


def _test_resolve_keeps_base_when_enabled() -> bool:
    """偏好为真或缺省时原样返回 base"""
    for sender_data in ({}, {SWITCH_KEY: True}):
        if _resolve(sender_data) is not MARKDOWN_ON_BASE:
            Logger.error(f"A user who keeps markdown on should get the base untouched, sender_data={sender_data}")
            return False
    return True


def _test_resolve_disables_markdown_features() -> bool:
    """偏好为假时关闭 markdown 相关能力"""
    resolved = _resolve({SWITCH_KEY: False})
    for name in (
        "support_markdown",
        "support_markdown_table",
        "support_action_text",
        "support_button",
        "use_url_md_format",
    ):
        if getattr(resolved, name) is not False:
            Logger.error(f"{name} should be off for a user who disabled markdown")
            return False
    # 与 markdown 无关的能力不应受牵连
    if resolved.support_image is not True:
        Logger.error("Disabling markdown must not touch unrelated capabilities")
        return False
    return True


def _test_resolve_keeps_toggle_available() -> bool:
    """关闭后该能力标志仍须为真

    标志一旦随之关闭，设置面板中的该行会消失，用户再无入口把 markdown 开回来。
    """
    if _resolve({SWITCH_KEY: False}).support_markdown_toggle is not True:
        Logger.error("support_markdown_toggle must survive the override, or the user cannot switch markdown back on")
        return False
    return True


def _test_resolve_composes_with_base() -> bool:
    """以既有的覆盖作 base 时，两种覆盖叠加而非互相顶替"""
    base = evolve(group_disable_read_all_message_features, support_markdown=True, support_markdown_toggle=True)
    resolved = _resolve({SWITCH_KEY: False}, base)
    if resolved.support_rss is not False or resolved.read_all_messages is not False:
        Logger.error("The base override must be preserved when layering the markdown override on top")
        return False
    if resolved.support_markdown is not False:
        Logger.error("The markdown override must still apply when layered onto a base override")
        return False
    return True


def _test_resolve_without_sender_union() -> bool:
    """没有用户 union 的会话（如主动推送）无从谈及偏好，取 base"""
    if _resolve(None) is not MARKDOWN_ON_BASE:
        Logger.error("Sessions without a sender union should keep the base untouched")
        return False
    return True


def _test_evolve_does_not_leak() -> bool:
    """覆盖须产出新实例，不得就地改写作为 base 的那一份"""
    before = MARKDOWN_ON_BASE.support_markdown
    _resolve({SWITCH_KEY: False})
    if MARKDOWN_ON_BASE.support_markdown is not before:
        Logger.error("resolve_features must not mutate the Features instance it was given")
        return False
    return True


class _FakeGroupMessage(GroupMessage):
    """替身群消息，绕过 SDK 的构造流程，仅记录发送时收到的参数。"""

    def __init__(self):
        self.id = "source-message"
        self.group_openid = "fake_group"
        self.message_scene = None
        self.reply_kwargs: list[dict] = []

    async def reply(self, **kwargs):
        self.reply_kwargs.append(kwargs)
        return {"id": "sent-1"}


async def _send_and_capture(support_markdown: bool) -> dict:
    """跑一遍发送流程，取回适配器交给平台的参数。

    ctx 取自 QQBotContextManager.context，按 session_id 登记替身即可驱动真实的发送路径。
    模块级的 qq_use_markdown 一并打桩为真，使该用例不受本地配置影响。

    消息须带上指令操作：send_msg_markdown() 对纯文本消息会主动退回纯文本路径，
    用纯文本作载荷则两种情形殊途同归，分辨不出发送路径究竟看的是什么。

    support_action_text 在两种情形下都保持为真，以便只让 support_markdown 一个变量变化。
    生产中二者由 resolve_features() 一同关闭，此处刻意拆开是为了把待测的那一条件隔离出来。

    :param support_markdown: 会话是否具备 markdown 能力。
    :return: reply() 收到的关键字参数。
    """
    session_id = f"markdown-send-{support_markdown}"
    session_info = SessionInfo(
        target_id=f"{target_group_prefix}|fake_group",
        sender_id="QQBot|1",
        target_from=target_group_prefix,
        client_name="QQBot",
        session_id=session_id,
        support_markdown=support_markdown,
        support_action_text=True,
    )
    ctx = _FakeGroupMessage()
    QQBotContextManager.context[session_id] = ctx
    try:
        with patch.object(qqbot_context, "qq_use_markdown", True):
            await QQBotContextManager.send_message(
                session_info,
                MessageChain.assign([Plain("hello "), ActionText("~help", show="帮助")]),
                quote=False,
            )
    finally:
        QQBotContextManager.context.pop(session_id, None)
    return ctx.reply_kwargs[0] if ctx.reply_kwargs else {}


async def _test_send_path_follows_session() -> bool:
    """发送路径须按会话而非仅按全局配置选择 markdown

    这一条守住整条链路的末端：能力覆盖得再对，发送时若仍只看模块级常量，用户的偏好便落空。
    """
    with_md = await _send_and_capture(True)
    without_md = await _send_and_capture(False)
    if "markdown" not in with_md:
        Logger.error(f"A markdown-capable session should be sent as markdown, got {sorted(with_md)}")
        return False
    if "markdown" in without_md:
        Logger.error(f"A session with markdown off must not be sent as markdown, got {sorted(without_md)}")
        return False
    if "content" not in without_md:
        Logger.error(f"A session with markdown off should fall back to plain content, got {sorted(without_md)}")
        return False
    return True


@func_case
async def test_markdown_toggle(tester: Tester):
    """bots.qqbot.features: 用户级 markdown 开关测试"""
    await tester.test(_test_feature_defaults_to_false, "能力默认不具备测试")
    await tester.test(_test_session_info_declares_field, "SessionInfo 声明该字段测试")
    await tester.test(_test_feature_injects_into_session, "特性可注入会话测试")
    await tester.test(_test_qqbot_follows_markdown_config, "QQBot 跟随全局配置测试")
    await tester.test(_test_resolve_keeps_base_when_enabled, "开启时保持默认能力测试")
    await tester.test(_test_resolve_disables_markdown_features, "关闭时禁用相关能力测试")
    await tester.test(_test_resolve_keeps_toggle_available, "关闭后仍可开回测试")
    await tester.test(_test_resolve_composes_with_base, "与既有覆盖叠加测试")
    await tester.test(_test_resolve_without_sender_union, "无用户 union 取默认测试")
    await tester.test(_test_evolve_does_not_leak, "覆盖不污染共享实例测试")
    await tester.test(_test_send_path_follows_session, "发送路径跟随会话测试")

    return tester
