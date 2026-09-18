"""静音策略：命令入口拦截与解除静音确认。"""

from unittest.mock import AsyncMock, patch

from core.builtins.message.chain import MessageChain
from core.builtins.parser.message import parser
from core.builtins.session.info import SessionInfo
from core.builtins.session.internal import MessageSession
from core.database.models import TargetUnionInfo
from core.queue.contracts import PlatformAPI
from core.tester import func_case, Tester
from core.tester.mock.factory import TestDataFactory

TARGET_ID = "TEST|Console|muted-policy"
SENDER_ID = "TEST|0"


async def _run_parser(text: str, *, muted: bool) -> list[str]:
    """把场景置为指定静音状态后，用真实 parser 跑一条消息并返回实际发出的消息链。"""
    await TestDataFactory.ensure_target(target_id=TARGET_ID, muted=muted)
    await TestDataFactory.ensure_sender(
        sender_id=SENDER_ID, superuser=True, sender_data={"typing_prompt": False, "typo_check": False}
    )
    sent: list[str] = []

    async def fake_send(session_info, chain, quote=True):
        sent.append(chain.to_kecode())
        return ["msg-id"]

    session_info = await SessionInfo.assign(
        target_id=TARGET_ID,
        target_from="TEST",
        client_name="TEST",
        sender_id=SENDER_ID,
        sender_from="TEST",
        messages=MessageChain.assign(text),
    )
    msg = MessageSession(session_info=session_info)
    with patch.object(PlatformAPI, "send_message", new=AsyncMock(side_effect=fake_send)):
        await parser(msg)
    return sent


async def _test_unmatched_command_silenced_when_muted():
    """静音时未匹配模块的命令也不再发出默认提示。"""
    if await _run_parser("~qqqzzzwww", muted=True):
        return False
    return bool(await _run_parser("~qqqzzzwww", muted=False))


async def _test_mute_command_still_replies():
    """静音命令本身在静音状态下仍可执行，切换后也能正常回复。"""
    sent = await _run_parser("~mute", muted=True)
    union = await TargetUnionInfo.get_by_target_id(TARGET_ID)
    if not sent or union.muted:
        return False
    sent = await _run_parser("~mute", muted=False)
    union = await TargetUnionInfo.get_by_target_id(TARGET_ID)
    return bool(sent) and union.muted


@func_case
async def test_muted_policy(tester: Tester):
    """parser 静音策略测试"""
    await tester.test(_test_unmatched_command_silenced_when_muted, "静音时未匹配命令静默")
    await tester.test(_test_mute_command_still_replies, "静音命令可执行并回复")
    return tester
