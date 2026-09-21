"""上报场景展开单元测试（需要数据库）。"""

from datetime import UTC, datetime, timedelta

from core.alive import Alive
from core.builtins.bot import Bot
from core.database.models import JobQueuePeersTable, TargetUnionBind, TargetUnionInfo
from core.tester import func_case, Tester

_CLIENT = "REPORTTEST"


async def _register_client():
    metadata = {
        "target_prefix_list": [f"{_CLIENT}|Group"],
        "sender_prefix_list": [_CLIENT],
    }
    lease_until = datetime.now(UTC) + timedelta(seconds=300)
    await JobQueuePeersTable.update_or_create(
        peer_id="TEST-PEER-REPORT",
        defaults={
            "role": "client",
            "service": _CLIENT,
            "state": "ready",
            "capabilities": ["rpc", "signals"],
            "metadata": metadata,
            "heartbeat_at": datetime.now(UTC),
            "lease_until": lease_until,
        },
    )
    Alive.refresh_peer(
        "TEST-PEER-REPORT",
        _CLIENT,
        metadata=metadata,
        lease_until=lease_until,
    )


async def _test_resolves_platform_id_to_union():
    union = await TargetUnionInfo.resolve_union("REPORTTEST|Group|resolve_a")
    return await Bot.resolve_union_targets(["REPORTTEST|Group|resolve_a"]) == [union.union_id]


async def _test_keeps_union_id_as_is():
    union = await TargetUnionInfo.resolve_union("REPORTTEST|Group|keep")
    return await Bot.resolve_union_targets([union.union_id]) == [union.union_id]


async def _test_union_id_leaves_no_stray_bind():
    union = await TargetUnionInfo.resolve_union("REPORTTEST|Group|stray")
    await Bot.resolve_union_targets([union.union_id])
    return not await TargetUnionBind.exists(target_id=union.union_id)


async def _test_unbound_target_dropped():
    return await Bot.resolve_union_targets(["REPORTTEST|Group|unbound"]) == []


async def _test_deduplicates_same_union():
    union = await TargetUnionInfo.resolve_union("REPORTTEST|Group|dedup_a")
    await union.bind_id("REPORTTEST|Group|dedup_b")

    resolved = await Bot.resolve_union_targets(["REPORTTEST|Group|dedup_a", "REPORTTEST|Group|dedup_b"])
    return resolved == [union.union_id]


async def _test_fetch_covers_all_union_members():
    await _register_client()
    union = await TargetUnionInfo.resolve_union("REPORTTEST|Group|fetch_a")
    await union.bind_id("REPORTTEST|Group|fetch_b")

    fetched = await Bot.fetch_union_target_list(["REPORTTEST|Group|fetch_a"])
    return {x.target_id for x in fetched} == {"REPORTTEST|Group|fetch_a", "REPORTTEST|Group|fetch_b"}


async def _test_fetch_accepts_single_value():
    await _register_client()
    union = await TargetUnionInfo.resolve_union("REPORTTEST|Group|single")
    fetched = await Bot.fetch_union_target_list(union.union_id)
    return [x.target_id for x in fetched] == ["REPORTTEST|Group|single"]


@func_case
async def test_report_targets(tester: Tester):
    """core: 上报场景按场景组展开"""
    alive = Alive.values.copy()
    try:
        await tester.test(_test_resolves_platform_id_to_union, "平台场景 ID 归一为场景组")
        await tester.test(_test_keeps_union_id_as_is, "场景组 ID 原样采用")
        await tester.test(_test_union_id_leaves_no_stray_bind, "归一组 ID 不留脏映射行")
        await tester.test(_test_unbound_target_dropped, "未登记场景略去")
        await tester.test(_test_deduplicates_same_union, "同组配置值去重")
        await tester.test(_test_fetch_covers_all_union_members, "取会话覆盖组内成员")
        await tester.test(_test_fetch_accepts_single_value, "接受单个场景 ID")
    finally:
        await JobQueuePeersTable.filter(peer_id="TEST-PEER-REPORT").delete()
        Alive.values.clear()
        Alive.values.update(alive)
    return tester
