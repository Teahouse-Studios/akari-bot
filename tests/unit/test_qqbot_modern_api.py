"""QQBot 适配器对 botpy 翻新接口的接入测试。"""

from botpy.protocol import MediaSendResult

from bots.qqbot.context import QQBotContextManager, _message_ids, _reply_target
from bots.qqbot.info import (
    target_c2c_prefix,
    target_direct_prefix,
    target_group_prefix,
    target_guild_prefix,
)
from core.builtins.session.info import SessionInfo
from core.logger import Logger
from core.tester import func_case, Tester


def _make_session(target_from: str, target: str = "target") -> SessionInfo:
    return SessionInfo(
        target_id=f"{target_from}|{target}",
        sender_id="QQBot|sender",
        target_from=target_from,
        client_name="QQBot",
        session_id=f"modern-{target_from}",
        message_id="source-message",
    )


def _test_reply_target_scopes() -> bool:
    expected = {
        target_c2c_prefix: "c2c",
        target_group_prefix: "group",
        target_guild_prefix: "channel",
        target_direct_prefix: "dm",
    }
    for target_from, scope in expected.items():
        session = _make_session(target_from)
        passive = _reply_target(session, object())
        proactive = _reply_target(session)
        if passive.scope != scope or passive.target_id != "target" or passive.message_id != "source-message":
            Logger.error(f"Unexpected passive target for {target_from}: {passive}")
            return False
        if proactive.scope != scope or proactive.message_id is not None:
            Logger.error(f"Unexpected proactive target for {target_from}: {proactive}")
            return False
    return True


def _test_message_id_collection() -> bool:
    result = [
        {"id": "plain"},
        MediaSendResult(upload={"file_info": "image"}, message={"id": "image"}),
        None,
    ]
    return _message_ids(result) == ["plain", "image"]


class _FakeClient:
    def __init__(self):
        self.recalls = []

    async def recall_message(self, target, message_id, *, hidetip=False):
        self.recalls.append((target, message_id, hidetip))


async def _test_c2c_delete_uses_unified_api() -> bool:
    client = _FakeClient()
    previous_client = QQBotContextManager.client
    QQBotContextManager.client = client
    try:
        await QQBotContextManager.delete_message(_make_session(target_c2c_prefix), ["one", "two"])
    finally:
        QQBotContextManager.client = previous_client
    if len(client.recalls) != 2:
        Logger.error(f"Expected two unified recall calls, got {client.recalls}")
        return False
    for target, message_id, hidetip in client.recalls:
        if target.scope != "c2c" or message_id not in ("one", "two") or hidetip:
            Logger.error(f"Unexpected C2C recall call: {(target, message_id, hidetip)}")
            return False
    return True


@func_case
async def test_qqbot_modern_api(tester: Tester):
    """bots.qqbot.context: botpy 翻新接口接入测试"""
    await tester.test(_test_reply_target_scopes, "统一回复目标映射测试")
    await tester.test(_test_message_id_collection, "高层发送结果消息 ID 提取测试")
    await tester.test(_test_c2c_delete_uses_unified_api, "C2C 统一撤回接口测试")
    return tester
