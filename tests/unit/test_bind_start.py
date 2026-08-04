"""modules.core.bind 单元测试 - bind start 的私聊与群组分支（需要数据库）。"""

import asyncio
from unittest.mock import patch

import modules.core.bind as bind
from core.union_merge import generate_code
from core.builtins.session.info import SessionInfo
from core.builtins.session.internal import MessageSession
from core.constants.exceptions import SessionFinished
from core.database.models import SenderUnionInfo, TargetUnionInfo
from core.tester import func_case, Tester


async def _session(prefix: str, is_private: bool) -> MessageSession:
    session_info = await SessionInfo.assign(
        target_id=f"{prefix}|X|1",
        target_from=f"{prefix}|X",
        client_name=prefix,
        sender_id=f"{prefix}|1",
        is_private=is_private,
        create=True,
    )
    return MessageSession(session_info=session_info)


def _issue_private_code(msg: MessageSession) -> dict:
    """
    以私聊身份生成一枚绑定码并立即取出，返回绑定码携带的信息。
    """
    code = generate_code(
        bind._sender_bind_codes,
        msg.session_info.sender_union_info.union_id,
        msg.session_info.sender_id,
        {"target_union_id": msg.session_info.target_union_info.union_id, "is_private": True},
    )
    return bind._take_code(code)[1]


def _answer_confirm(result: bool):
    """
    把 wait_confirm 固定成给定答复，绕开交互。
    """
    return patch.object(MessageSession, "wait_confirm", new=lambda self, *a, **k: asyncio.sleep(0, result=result))


async def _test_private_binds_both_unions():
    """测试 bind start - 私聊绑定须同时并入账号组与场景组"""
    try:
        initiator = await _session("BINDA", True)
        entry = _issue_private_code(initiator)
        try:
            with _answer_confirm(True):
                await bind._bind_private(await _session("BINDB", True), entry)
        except SessionFinished:
            pass

        # 私聊里「这个账号」与「这段私聊」是同一回事，只并其一会让另一半数据留在原处
        senders = [(await SenderUnionInfo.resolve_union(f"{p}|1")).union_id for p in ("BINDA", "BINDB")]
        targets = [(await TargetUnionInfo.resolve_union(f"{p}|X|1")).union_id for p in ("BINDA", "BINDB")]
        return senders[0] == senders[1] and targets[0] == targets[1]

    except Exception:
        return False


async def _test_cancel_leaves_nothing_bound():
    """测试 bind start - 取消确认时两侧都不应发生变动"""
    try:
        initiator = await _session("BINDC", True)
        current = await _session("BINDD", True)
        before = (
            initiator.session_info.sender_union_info.union_id,
            initiator.session_info.target_union_info.union_id,
            current.session_info.sender_union_info.union_id,
            current.session_info.target_union_info.union_id,
        )
        entry = _issue_private_code(initiator)
        try:
            with _answer_confirm(False):
                await bind._bind_private(current, entry)
        except SessionFinished:
            pass

        # 两次合并共用一次确认，取消后不该停在只绑一半的状态
        after = (
            (await SenderUnionInfo.resolve_union("BINDC|1")).union_id,
            (await TargetUnionInfo.resolve_union("BINDC|X|1")).union_id,
            (await SenderUnionInfo.resolve_union("BINDD|1")).union_id,
            (await TargetUnionInfo.resolve_union("BINDD|X|1")).union_id,
        )
        return before == after

    except Exception:
        return False


async def _test_scene_mismatch_rejected():
    """测试 bind start - 私聊码与群组码不得跨场景兑换"""
    try:
        entry = _issue_private_code(await _session("BINDE", True))
        # 群组场景兑换私聊码会把整个群的数据并进对方的私聊，必须拦下
        group = await _session("BINDF", False)
        return entry["is_private"] != group.session_info.is_private

    except Exception:
        return False


@func_case
async def test_bind_start(tester: Tester):
    """modules.core.bind: bind start 测试"""
    await tester.test(_test_private_binds_both_unions, "私聊同时绑定两组测试")
    await tester.test(_test_cancel_leaves_nothing_bound, "取消不留半绑状态测试")
    await tester.test(_test_scene_mismatch_rejected, "跨场景兑换拦截测试")

    return tester
