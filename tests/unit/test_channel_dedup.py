"""core.builtins.parser.message 单元测试 - 消息通道去重（需要数据库）。"""

from types import SimpleNamespace

from core.builtins.parser.message import CHANNEL_DEDUP_WINDOW, _claim_channel_message, channel_claim_cache
from core.database.models import TargetUnionInfo, TargetUnionBind
from core.tester import func_case, Tester


async def _fake_msg(target_id: str, trigger: str):
    """
    构造一个满足 _claim_channel_message 所需的最小会话：该函数仅读取场景组、通道号与命令文本。
    """
    target_union_info = await TargetUnionInfo.resolve_union(target_id)
    return SimpleNamespace(
        session_info=SimpleNamespace(
            target_id=target_id,
            target_union_id=target_union_info.union_id,
            target_channel_id=target_union_info.bind.channel_id,
        ),
        trigger_msg=trigger,
    )


async def _test_alone_in_channel_never_claims():
    """测试消息通道 - 通道内仅有自身时不作认领"""
    try:
        msg = await _fake_msg("CHANTEST|Group|alone", "help")
        # 连续两次均不应判定为重复，否则单个场景会丢弃自身的消息。
        return not await _claim_channel_message(msg) and not await _claim_channel_message(msg)

    except Exception:
        return False


async def _test_same_channel_claims_once():
    """测试消息通道 - 同通道内由先到者认领，后到者避让"""
    try:
        union = await TargetUnionInfo.resolve_union("CHANTEST|Group|dup1")
        await union.bind_id("CHANTEST|Group|dup2")
        await TargetUnionBind.filter(union_id=union.union_id).update(channel_id=1)

        first = await _fake_msg("CHANTEST|Group|dup1", "help")
        second = await _fake_msg("CHANTEST|Group|dup2", "help")

        return not await _claim_channel_message(first) and await _claim_channel_message(second)

    except Exception:
        return False


async def _test_repeat_from_same_session_not_duplicate():
    """测试消息通道 - 同一场景在时间窗内重发不判定为重复"""
    try:
        union = await TargetUnionInfo.resolve_union("CHANTEST|Group|rep1")
        await union.bind_id("CHANTEST|Group|rep2")
        await TargetUnionBind.filter(union_id=union.union_id).update(channel_id=1)

        first = await _fake_msg("CHANTEST|Group|rep1", "echo")
        peer = await _fake_msg("CHANTEST|Group|rep2", "echo")

        # 认领键只由通道与内容组成，不含发起方，重发的消息会撞上自身上一条留下的认领。
        if await _claim_channel_message(first) or await _claim_channel_message(first):
            return False
        # 重发之后同通道的其它场景仍应避让，否则同一条消息会被响应两次。
        return await _claim_channel_message(peer)

    except Exception:
        return False


async def _test_outside_window_not_duplicate():
    """测试消息通道 - 超出时间窗的相同文本不判定为重复"""
    try:
        union = await TargetUnionInfo.resolve_union("CHANTEST|Group|win1")
        await union.bind_id("CHANTEST|Group|win2")
        await TargetUnionBind.filter(union_id=union.union_id).update(channel_id=1)

        first = await _fake_msg("CHANTEST|Group|win1", "ping")
        second = await _fake_msg("CHANTEST|Group|win2", "ping")

        if await _claim_channel_message(first):
            return False

        # 将认领时间回拨至时间窗之外，模拟间隔较长后再次发送同样的消息。
        for entry in channel_claim_cache.data.values():
            if "timestamp" in entry:
                entry["timestamp"] -= CHANNEL_DEDUP_WINDOW * 2

        return not await _claim_channel_message(second)

    except Exception:
        return False


async def _test_different_channel_not_duplicate():
    """测试消息通道 - 同组但不同通道互不干扰"""
    try:
        union = await TargetUnionInfo.resolve_union("CHANTEST|Group|sep1")
        await union.bind_id("CHANTEST|Group|sep2")

        first = await _fake_msg("CHANTEST|Group|sep1", "version")
        second = await _fake_msg("CHANTEST|Group|sep2", "version")

        # bind_id 默认逐个递增编号，两个场景本就不同号，均不应丢弃对方的消息。
        return not await _claim_channel_message(first) and not await _claim_channel_message(second)

    except Exception:
        return False


@func_case
async def test_channel_dedup(tester: Tester):
    """core.builtins.parser.message: 消息通道去重测试"""
    await tester.test(_test_alone_in_channel_never_claims, "单场景不认领测试")
    await tester.test(_test_same_channel_claims_once, "同通道抢占测试")
    await tester.test(_test_repeat_from_same_session_not_duplicate, "同场景重发测试")
    await tester.test(_test_outside_window_not_duplicate, "超出时间窗测试")
    await tester.test(_test_different_channel_not_duplicate, "不同通道互不干扰测试")

    return tester
