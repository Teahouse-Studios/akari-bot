"""modules.core.hooks.routing 单元测试 - 消息通道去重（需要数据库）。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from core.builtins.parser.hooks import HookPoint, Stop, dispatch_parser_hook
from core.database.models import TargetUnionInfo, TargetUnionBind
from core.tester import func_case, Tester
from modules.core.hooks.routing import CHANNEL_DEDUP_WINDOW, channel_claim_cache


async def _fake_msg(target_id: str, trigger: str):
    target_union_info = await TargetUnionInfo.resolve_union(target_id)
    return SimpleNamespace(
        session_info=SimpleNamespace(
            target_id=target_id,
            target_from="CHANTEST|Group",
            client_name="CHANTEST",
            target_union_id=target_union_info.union_id,
            target_channel_id=target_union_info.bind.channel_id,
        ),
        trigger_msg=trigger,
    )


async def _claim(msg) -> bool:
    outcome = await dispatch_parser_hook(HookPoint.CHANNEL_CLAIM, msg)
    return isinstance(outcome.result, Stop)


async def _test_alone_in_channel_never_claims():
    try:
        msg = await _fake_msg("CHANTEST|Group|alone", "help")
        # 连续两次均不应判定为重复，否则单个场景会丢弃自身的消息。
        return not await _claim(msg) and not await _claim(msg)

    except Exception:
        return False


async def _test_same_channel_claims_once():
    try:
        union = await TargetUnionInfo.resolve_union("CHANTEST|Group|dup1")
        await union.bind_id("CHANTEST|Group|dup2")
        await TargetUnionBind.filter(union_id=union.union_id).update(channel_id=1)

        first = await _fake_msg("CHANTEST|Group|dup1", "help")
        second = await _fake_msg("CHANTEST|Group|dup2", "help")

        return not await _claim(first) and await _claim(second)

    except Exception:
        return False


async def _test_repeat_from_same_session_not_duplicate():
    try:
        union = await TargetUnionInfo.resolve_union("CHANTEST|Group|rep1")
        await union.bind_id("CHANTEST|Group|rep2")
        await TargetUnionBind.filter(union_id=union.union_id).update(channel_id=1)

        first = await _fake_msg("CHANTEST|Group|rep1", "echo")
        peer = await _fake_msg("CHANTEST|Group|rep2", "echo")

        # 认领键只由通道与内容组成，不含发起方，重发的消息会撞上自身上一条留下的认领。
        if await _claim(first) or await _claim(first):
            return False
        # 重发之后同通道的其它场景仍应避让，否则同一条消息会被响应两次。
        return await _claim(peer)

    except Exception:
        return False


async def _test_outside_window_not_duplicate():
    try:
        union = await TargetUnionInfo.resolve_union("CHANTEST|Group|win1")
        await union.bind_id("CHANTEST|Group|win2")
        await TargetUnionBind.filter(union_id=union.union_id).update(channel_id=1)

        first = await _fake_msg("CHANTEST|Group|win1", "ping")
        second = await _fake_msg("CHANTEST|Group|win2", "ping")

        if await _claim(first):
            return False

        # 将认领时间回拨至时间窗之外，模拟间隔较长后再次发送同样的消息。
        for entry in channel_claim_cache.data.values():
            if "timestamp" in entry:
                entry["timestamp"] -= CHANNEL_DEDUP_WINDOW * 2

        return not await _claim(second)

    except Exception:
        return False


async def _test_different_channel_not_duplicate():
    try:
        union = await TargetUnionInfo.resolve_union("CHANTEST|Group|sep1")
        await union.bind_id("CHANTEST|Group|sep2")

        first = await _fake_msg("CHANTEST|Group|sep1", "version")
        second = await _fake_msg("CHANTEST|Group|sep2", "version")

        # bind_id 默认逐个递增编号，两个场景本就不同号，均不应丢弃对方的消息。
        return not await _claim(first) and not await _claim(second)

    except Exception:
        return False


async def _test_channel_lookup_failure_stops_message():
    msg = await _fake_msg("CHANTEST|Group|lookup-failed", "help")
    with patch.object(TargetUnionBind, "list_channels", new=AsyncMock(side_effect=RuntimeError("db failed"))):
        return await _claim(msg)


@func_case
async def test_channel_dedup(tester: Tester):
    """modules.core.hooks.routing: 消息通道去重测试"""
    await tester.test(_test_alone_in_channel_never_claims, "单场景不认领测试")
    await tester.test(_test_same_channel_claims_once, "同通道抢占测试")
    await tester.test(_test_repeat_from_same_session_not_duplicate, "同场景重发测试")
    await tester.test(_test_outside_window_not_duplicate, "超出时间窗测试")
    await tester.test(_test_different_channel_not_duplicate, "不同通道互不干扰测试")
    await tester.test(_test_channel_lookup_failure_stops_message, "通道查询失败停止消息测试")

    return tester
