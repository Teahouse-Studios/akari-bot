"""上报场景展开单元测试（需要数据库）。

`report_targets` 配置的是场景组，上报须落到该组下的全部平台场景：同一现实场景的多个
平台入口由 pick_channel_heads 归拢为一条并互为后备，配置项所指的那个客户端掉线时仍有
下一跳可换。此前的实现把配置值直接当作平台场景 ID 去取会话，组内其余成员完全不参与，
next_hops 恒为空，该客户端一掉线整条上报即静默丢失。

组内展开与退役滤除统一收在 fetch_union_target_list，按场景组推送的
send_direct_message_to_union_target 亦走这条路，其行为另由 test_union_push.py 守住。
"""

from core.alive import Alive
from core.builtins.bot import Bot
from core.database.models import TargetUnionBind, TargetUnionInfo
from core.tester import func_case, Tester

_CLIENT = "REPORTTEST"


def _register_client():
    """将本文件所用的客户端登记进保活表。

    取会话时须由保活表反查场景所属的客户端，未登记者取不出会话。保活表非空时
    ``Alive.determine_client(None)`` 还会直接抛错，而 ``fetch_target`` 会将其吞下，
    表现为无声地少了几个会话。
    """
    Alive.refresh_alive(_CLIENT, target_prefix_list=[f"{_CLIENT}|Group"], sender_prefix_list=[_CLIENT])


async def _test_resolves_platform_id_to_union():
    """配置平台场景 ID 时应归一为其所属场景组的 union ID。"""
    union = await TargetUnionInfo.resolve_union("REPORTTEST|Group|resolve_a")
    return await Bot.resolve_union_targets(["REPORTTEST|Group|resolve_a"]) == [union.union_id]


async def _test_keeps_union_id_as_is():
    """配置场景组 ID 时应原样采用，不再二次解析。"""
    union = await TargetUnionInfo.resolve_union("REPORTTEST|Group|keep")
    return await Bot.resolve_union_targets([union.union_id]) == [union.union_id]


async def _test_union_id_leaves_no_stray_bind():
    """归一场景组 ID 不应为组 ID 自身建出映射行。"""
    union = await TargetUnionInfo.resolve_union("REPORTTEST|Group|stray")
    await Bot.resolve_union_targets([union.union_id])
    return not await TargetUnionBind.exists(target_id=union.union_id)


async def _test_unbound_target_dropped():
    """尚未登记 union 的场景无从解析，应略去而非原样带入。"""
    return await Bot.resolve_union_targets(["REPORTTEST|Group|unbound"]) == []


async def _test_deduplicates_same_union():
    """同属一个场景组的多个配置值只应归一出一份，避免重复上报。"""
    union = await TargetUnionInfo.resolve_union("REPORTTEST|Group|dedup_a")
    await union.bind_id("REPORTTEST|Group|dedup_b")

    resolved = await Bot.resolve_union_targets(["REPORTTEST|Group|dedup_a", "REPORTTEST|Group|dedup_b"])
    return resolved == [union.union_id]


async def _test_fetch_covers_all_union_members():
    """按场景组取会话时，组内其余成员亦应在列，方能互为后备。"""
    _register_client()
    union = await TargetUnionInfo.resolve_union("REPORTTEST|Group|fetch_a")
    await union.bind_id("REPORTTEST|Group|fetch_b")

    fetched = await Bot.fetch_union_target_list(["REPORTTEST|Group|fetch_a"])
    return {x.target_id for x in fetched} == {"REPORTTEST|Group|fetch_a", "REPORTTEST|Group|fetch_b"}


async def _test_fetch_accepts_single_value():
    """单个场景 ID 亦应接受，与按场景组推送的入参形态一致。"""
    _register_client()
    union = await TargetUnionInfo.resolve_union("REPORTTEST|Group|single")
    fetched = await Bot.fetch_union_target_list(union.union_id)
    return [x.target_id for x in fetched] == ["REPORTTEST|Group|single"]


@func_case
async def test_report_targets(tester: Tester):
    """core: 上报场景按场景组展开"""
    await tester.test(_test_resolves_platform_id_to_union, "平台场景 ID 归一为场景组")
    await tester.test(_test_keeps_union_id_as_is, "场景组 ID 原样采用")
    await tester.test(_test_union_id_leaves_no_stray_bind, "归一组 ID 不留脏映射行")
    await tester.test(_test_unbound_target_dropped, "未登记场景略去")
    await tester.test(_test_deduplicates_same_union, "同组配置值去重")
    await tester.test(_test_fetch_covers_all_union_members, "取会话覆盖组内成员")
    await tester.test(_test_fetch_accepts_single_value, "接受单个场景 ID")
    return tester
