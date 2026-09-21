"""用户级 markdown 消息开关的单元测试。"""

from unittest.mock import patch

from attr import evolve
from botpy.message import GroupMessage

import bots.qqbot.context as qqbot_context
import bots.qqbot.features as qqbot_features_module
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

SWITCH_KEY = "use_markdown"

# 平台能力集在导入时即依配置定型，qq_use_markdown 为假的部署上，markdown 相关能力全为假，
# 因此无法验证覆盖逻辑。各用例另建一份启用 Markdown 的基准并替换该开关，
# 使断言只考察覆盖逻辑本身，不受本地配置左右。
MARKDOWN_ON_BASE = evolve(
    qqbot_features,
    support_markdown=True,
    support_markdown_extension=True,
    support_action_text=True,
    support_button=True,
    support_markdown_toggle=True,
    use_url_md_format=True,
)


def _resolve(sender_data: dict | None, base: Features = MARKDOWN_ON_BASE) -> Features:
    with patch.object(qqbot_features_module, "qq_use_markdown", True):
        return resolve_features(_make_session(sender_data), base)


def _make_session(sender_data: dict | None) -> SessionInfo:
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


async def _test_feature_injects_into_session() -> bool:
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


def _test_resolve_keeps_base_when_enabled() -> bool:
    for sender_data in ({}, {SWITCH_KEY: True}):
        if _resolve(sender_data) is not MARKDOWN_ON_BASE:
            Logger.error(f"A user who keeps markdown on should get the base untouched, sender_data={sender_data}")
            return False
    return True


def _test_resolve_disables_markdown_features() -> bool:
    resolved = _resolve({SWITCH_KEY: False})
    for name in (
        "support_markdown",
        "support_markdown_extension",
        "support_handle_message_nodes",
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
    if _resolve({SWITCH_KEY: False}).support_markdown_toggle is not True:
        Logger.error("support_markdown_toggle must survive the override, or the user cannot switch markdown back on")
        return False
    return True


def _test_resolve_composes_with_base() -> bool:
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
    if _resolve(None) is not MARKDOWN_ON_BASE:
        Logger.error("Sessions without a sender union should keep the base untouched")
        return False
    return True


def _test_evolve_does_not_leak() -> bool:
    before = MARKDOWN_ON_BASE.support_markdown
    _resolve({SWITCH_KEY: False})
    if MARKDOWN_ON_BASE.support_markdown is not before:
        Logger.error("resolve_features must not mutate the Features instance it was given")
        return False
    return True


class _FakeGroupMessage(GroupMessage):
    def __init__(self):
        self.id = "source-message"
        self.group_openid = "fake_group"
        self.message_context = None


class _FakeClient:
    def __init__(self):
        self.calls: list[dict] = []

    async def send(self, target, **kwargs):
        self.calls.append(kwargs)
        return {"id": "sent-1"}

    async def send_markdown(self, target, content, keyboard=None):
        self.calls.append({"markdown": {"content": content}, "keyboard": keyboard})
        return {"id": "sent-1"}


async def _send_and_capture(support_markdown: bool) -> dict:
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
    client = _FakeClient()
    QQBotContextManager.context[session_id] = ctx
    try:
        with (
            patch.object(qqbot_context, "qq_use_markdown", True),
            patch.object(QQBotContextManager, "client", client),
        ):
            await QQBotContextManager.send_message(
                session_info,
                MessageChain.assign([Plain("hello "), ActionText("~help", show="帮助")]),
                quote=False,
            )
    finally:
        QQBotContextManager.context.pop(session_id, None)
    return client.calls[0] if client.calls else {}


async def _test_send_path_follows_session() -> bool:
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
    await tester.test(_test_feature_injects_into_session, "特性可注入会话测试")
    await tester.test(_test_resolve_keeps_base_when_enabled, "开启时保持默认能力测试")
    await tester.test(_test_resolve_disables_markdown_features, "关闭时禁用相关能力测试")
    await tester.test(_test_resolve_keeps_toggle_available, "关闭后仍可开回测试")
    await tester.test(_test_resolve_composes_with_base, "与既有覆盖叠加测试")
    await tester.test(_test_resolve_without_sender_union, "无用户 union 取默认测试")
    await tester.test(_test_evolve_does_not_leak, "覆盖不污染共享实例测试")
    await tester.test(_test_send_path_follows_session, "发送路径跟随会话测试")

    return tester
