"""core.database.models 单元测试 - union 绑定（需要数据库）。"""

import asyncio
from unittest.mock import AsyncMock, patch

from core.builtins.session.info import SessionInfo
from core.database.models import (
    AnalyticsData,
    SenderUnionInfo,
    SenderUnionBind,
    TargetUnionInfo,
    TargetUnionBind,
    UnionDeleteBlocked,
)
from core.loader import ModulesManager
from core.tester import func_case, Tester
from core.types import Module


async def _test_resolve_union_creates_bind():
    """测试 resolve_union - 首次解析建出 union 与映射"""
    try:
        union = await SenderUnionInfo.resolve_union("UNIONTEST|resolve|1")
        if not union:
            return False
        bind = await SenderUnionBind.get_or_none(sender_id="UNIONTEST|resolve|1")
        if not bind or bind.union_id != union.union_id:
            return False

        # 同一个 ID 再解析应拿到同一个 union，而非另建一份。
        again = await SenderUnionInfo.resolve_union("UNIONTEST|resolve|1")
        return again.union_id == union.union_id

    except Exception:
        return False


async def _test_resolve_union_concurrent_same_id():
    """测试 resolve_union - 同一新 ID 并发解析只创建一组，且调用均成功。"""
    platform_id = "UNIONTEST|concurrent|same"
    results = await asyncio.gather(
        *(SenderUnionInfo.resolve_union(platform_id) for _ in range(20)),
        return_exceptions=True,
    )
    if any(isinstance(result, BaseException) for result in results):
        return False

    union_ids = {result.union_id for result in results}
    if len(union_ids) != 1:
        return False

    union_id = union_ids.pop()
    return (
        await SenderUnionBind.filter(sender_id=platform_id, union_id=union_id).count() == 1
        and await SenderUnionInfo.filter(union_id=union_id).count() == 1
    )


async def _test_new_union_id_prefixed():
    """测试 new_union_id - 新建的 union ID 带域前缀且为大写"""
    try:
        sender = await SenderUnionInfo.resolve_union("UNIONTEST|prefix|1")
        target = await TargetUnionInfo.resolve_union("UNIONTEST|Group|prefix")
        for union_id, prefix in ((sender.union_id, "USID|"), (target.union_id, "UTID|")):
            if not union_id.startswith(prefix) or union_id != union_id.upper():
                return False

        # 解绑拆出的 union 同样须带前缀。
        await sender.bind_id("UNIONTEST|prefix|2")
        split = await sender.unbind_id("UNIONTEST|prefix|2")
        return bool(split) and split.union_id.startswith("USID|") and split.union_id == split.union_id.upper()

    except Exception:
        return False


async def _test_resolve_union_no_create():
    """测试 resolve_union - create 为 False 时不建行"""
    try:
        union = await SenderUnionInfo.resolve_union("UNIONTEST|nocreate|1", create=False)
        if union:
            return False
        return not await SenderUnionBind.exists(sender_id="UNIONTEST|nocreate|1")

    except Exception:
        return False


async def _test_bind_id_shares_data():
    """测试 bind_id - 绑定后两个账号共享同一份数据"""
    try:
        first = await SenderUnionInfo.resolve_union("UNIONTEST|share|1")
        first.petal = 42
        await first.save()

        if not await first.bind_id("UNIONTEST|share|2"):
            return False

        second = await SenderUnionInfo.resolve_union("UNIONTEST|share|2")
        if second.union_id != first.union_id or second.petal != 42:
            return False

        bound = sorted(await first.list_bound_ids())
        return bound == ["UNIONTEST|share|1", "UNIONTEST|share|2"]

    except Exception:
        return False


async def _test_bind_id_rejects_other_union():
    """测试 bind_id - 已属于其他 union 的账号不可重复绑定"""
    try:
        first = await SenderUnionInfo.resolve_union("UNIONTEST|reject|1")
        await SenderUnionInfo.resolve_union("UNIONTEST|reject|2")
        return not await first.bind_id("UNIONTEST|reject|2")

    except Exception:
        return False


async def _test_bind_id_concurrent_claim_returns_boolean():
    """测试 bind_id - 两个 union 并发争用同一账号时一胜一负，不向调用方泄漏唯一键异常。"""
    first = await SenderUnionInfo.resolve_union("UNIONTEST|claim|owner1")
    second = await SenderUnionInfo.resolve_union("UNIONTEST|claim|owner2")
    claimed_id = "UNIONTEST|claim|shared"

    results = await asyncio.gather(
        first.bind_id(claimed_id),
        second.bind_id(claimed_id),
        return_exceptions=True,
    )
    if any(isinstance(result, BaseException) for result in results):
        return False
    bind = await SenderUnionBind.get_or_none(sender_id=claimed_id)
    return sorted(results) == [False, True] and bind.union_id in {first.union_id, second.union_id}


async def _test_counter_updates_are_atomic():
    """测试用户计数器 - 并发警告和花瓣增量不会因过期实例整行保存而丢失。"""
    sender_id = "UNIONTEST|counter|1"
    union = await SenderUnionInfo.resolve_union(sender_id)
    union.warns = 0
    union.petal = 0
    await union.save()

    warn_instances = await asyncio.gather(*(SenderUnionInfo.get_by_sender_id(sender_id) for _ in range(20)))
    petal_instances = await asyncio.gather(*(SenderUnionInfo.get_by_sender_id(sender_id) for _ in range(20)))
    await asyncio.gather(*(instance.warn_user() for instance in warn_instances))
    await asyncio.gather(*(instance.modify_petal(2) for instance in petal_instances))

    refreshed = await SenderUnionInfo.get_by_sender_id(sender_id)
    return refreshed.warns == 20 and refreshed.petal == 40


async def _test_json_updates_preserve_concurrent_keys():
    """测试 Union JSON 数据 - 并发修改不同键时不会用过期快照覆盖其它协程。"""
    sender_id = "UNIONTEST|json|sender"
    target_id = "UNIONTEST|Group|json-target"
    sender = await SenderUnionInfo.resolve_union(sender_id)
    target = await TargetUnionInfo.resolve_union(target_id)
    sender.sender_data = {}
    target.target_data = {}
    await sender.save()
    await target.save()

    sender_instances = await asyncio.gather(*(SenderUnionInfo.get_by_sender_id(sender_id) for _ in range(20)))
    target_instances = await asyncio.gather(*(TargetUnionInfo.get_by_target_id(target_id) for _ in range(20)))
    await asyncio.gather(
        *(instance.edit_sender_data(f"key-{index}", index) for index, instance in enumerate(sender_instances))
    )
    await asyncio.gather(
        *(instance.edit_target_data(f"key-{index}", index) for index, instance in enumerate(target_instances))
    )

    refreshed_sender = await SenderUnionInfo.get_by_sender_id(sender_id)
    refreshed_target = await TargetUnionInfo.get_by_target_id(target_id)
    expected = {f"key-{index}": index for index in range(20)}
    return refreshed_sender.sender_data == expected and refreshed_target.target_data == expected


async def _test_permission_lists_preserve_concurrent_members():
    """测试场景权限列表 - 并发加入不同成员时不丢失先完成的更新。"""
    target_id = "UNIONTEST|Group|permission-list"
    target = await TargetUnionInfo.resolve_union(target_id)
    target.custom_admins = []
    target.banned_users = []
    await target.save()

    admin_instances = await asyncio.gather(*(TargetUnionInfo.get_by_target_id(target_id) for _ in range(20)))
    banned_instances = await asyncio.gather(*(TargetUnionInfo.get_by_target_id(target_id) for _ in range(20)))
    await asyncio.gather(
        *(instance.config_custom_admin(f"USID|ADMIN-{index}") for index, instance in enumerate(admin_instances))
    )
    await asyncio.gather(
        *(instance.config_banned_user(f"USID|BANNED-{index}") for index, instance in enumerate(banned_instances))
    )

    refreshed = await TargetUnionInfo.get_by_target_id(target_id)
    return len(refreshed.custom_admins) == 20 and len(refreshed.banned_users) == 20


async def _test_block_applies_to_whole_union():
    """测试封禁范围 - 封禁挂在 union 上，组内全部账号一并生效"""
    try:
        union = await SenderUnionInfo.resolve_union("UNIONTEST|blocked|1")
        await union.bind_id("UNIONTEST|blocked|2")
        await union.edit_attr("blocked", True)

        # 组内任一账号解析出的都是同一行，换账号绕不过封禁。
        first = await SenderUnionInfo.resolve_union("UNIONTEST|blocked|1")
        second = await SenderUnionInfo.resolve_union("UNIONTEST|blocked|2")
        return first.blocked and second.blocked

    except Exception:
        return False


async def _test_merge_keeps_block():
    """测试封禁范围 - 与干净组合并后封禁不被稀释"""
    try:
        blocked = await SenderUnionInfo.resolve_union("UNIONTEST|mergeban|1")
        await blocked.edit_attr("blocked", True)
        clean = await SenderUnionInfo.resolve_union("UNIONTEST|mergeban|2")

        # 合并只会把封禁传染给对方，不存在借合并洗白的方向。
        merged = await clean.merge_union(blocked)
        both = [await SenderUnionInfo.resolve_union(f"UNIONTEST|mergeban|{i}") for i in (1, 2)]
        return merged.blocked and all(u.blocked for u in both)

    except Exception:
        return False


async def _test_unbind_keeps_block_and_binding():
    """测试封禁范围 - 解绑后封禁随账号转移，且映射行始终存在"""
    try:
        union = await SenderUnionInfo.resolve_union("UNIONTEST|unbindban|1")
        await union.bind_id("UNIONTEST|unbindban|2")
        await union.edit_attr("blocked", True)

        fresh = await SenderUnionInfo.resolve_union("UNIONTEST|unbindban|1")
        split = await fresh.unbind_id("UNIONTEST|unbindban|2")

        # 映射行改挂而非重建：拆出的账号在任一时刻都能解析回一个已封禁的组，
        # 不会因缺少映射行而被当作新账号另建干净组。
        bind = await SenderUnionBind.get_or_none(sender_id="UNIONTEST|unbindban|2")
        again = await SenderUnionInfo.resolve_union("UNIONTEST|unbindban|2")
        return split.blocked and again.blocked and bind.union_id == split.union_id

    except Exception:
        return False


async def _test_unblock_applies_to_whole_union():
    """测试解封 - 解封同样作用于整组"""
    try:
        union = await SenderUnionInfo.resolve_union("UNIONTEST|unblock|1")
        await union.bind_id("UNIONTEST|unblock|2")
        await union.edit_attr("blocked", True)

        blocked_side = await SenderUnionInfo.resolve_union("UNIONTEST|unblock|2")
        await blocked_side.edit_attr("blocked", False)

        again = await SenderUnionInfo.resolve_union("UNIONTEST|unblock|2")
        other = await SenderUnionInfo.resolve_union("UNIONTEST|unblock|1")
        return not again.blocked and not other.blocked

    except Exception:
        return False


async def _test_switch_identity_unblocks():
    """测试 switch_identity - 取消身份时解除封禁"""
    try:
        union = await SenderUnionInfo.resolve_union("UNIONTEST|identity|1")
        await union.switch_identity(trust=False, enable=True)
        if not (await SenderUnionInfo.resolve_union("UNIONTEST|identity|1")).blocked:
            return False

        blocked_side = await SenderUnionInfo.resolve_union("UNIONTEST|identity|1")
        await blocked_side.switch_identity(trust=False, enable=False)

        again = await SenderUnionInfo.resolve_union("UNIONTEST|identity|1")
        return not again.blocked

    except Exception:
        return False


async def _test_merge_union_creates_new_union():
    """测试 merge_union - 合并生成全新的组，两个旧组一并作废"""
    try:
        first = await SenderUnionInfo.resolve_union("UNIONTEST|newid|1")
        second = await SenderUnionInfo.resolve_union("UNIONTEST|newid|2")

        merged = await first.merge_union(second)
        if not merged:
            return False
        # 不沿用任何一方的组 ID，合并方向才不存在歧义。
        if merged.union_id in (first.union_id, second.union_id):
            return False
        if await SenderUnionInfo.exists(union_id=first.union_id) or await SenderUnionInfo.exists(
            union_id=second.union_id
        ):
            return False

        return sorted(await merged.list_bound_ids()) == ["UNIONTEST|newid|1", "UNIONTEST|newid|2"]

    except Exception:
        return False


async def _test_merge_union_merges_data():
    """测试 merge_union - 花瓣累加、警告取最大、数据逐键合并"""
    try:
        keep = await SenderUnionInfo.resolve_union("UNIONTEST|merge|1")
        keep.petal = 10
        keep.warns = 1
        keep.sender_data = {"shared": "keep", "only_keep": 1}
        await keep.save()

        drop = await SenderUnionInfo.resolve_union("UNIONTEST|merge|2")
        drop.petal = 5
        drop.warns = 3
        drop.superuser = True
        drop.sender_data = {"shared": "drop", "only_drop": 2}
        await drop.save()

        merged = await keep.merge_union(drop)

        if merged.petal != 15 or merged.warns != 3 or not merged.superuser:
            return False
        # 键冲突保留发起方，不冲突的键则一并带过来。
        if merged.sender_data != {"shared": "keep", "only_keep": 1, "only_drop": 2}:
            return False
        if await SenderUnionInfo.exists(union_id=drop.union_id):
            return False

        bound = sorted(await merged.list_bound_ids())
        return bound == ["UNIONTEST|merge|1", "UNIONTEST|merge|2"]

    except Exception:
        return False


async def _test_merge_union_rewrites_permission_refs():
    """测试 merge_union - 权限名单中的旧 union ID 被改写"""
    try:
        keep = await SenderUnionInfo.resolve_union("UNIONTEST|refs|1")
        drop = await SenderUnionInfo.resolve_union("UNIONTEST|refs|2")

        target = await TargetUnionInfo.resolve_union("UNIONTEST|Group|refs")
        target.custom_admins = [drop.union_id]
        target.banned_users = [keep.union_id]
        await target.save()

        merged = await keep.merge_union(drop)

        # 两侧的旧 ID 均须改写至新组，遗漏任何一侧都会导致管理员身份丢失。
        after = await TargetUnionInfo.resolve_union("UNIONTEST|Group|refs")
        return after.custom_admins == [merged.union_id] and after.banned_users == [merged.union_id]

    except Exception:
        return False


async def _test_merge_union_moves_module_rows():
    """测试 merge_union - 模块表随之改挂新 union"""
    try:
        from modules.phigros.database.models import PhigrosBindInfo

        keep = await SenderUnionInfo.resolve_union("UNIONTEST|modmove|1")
        drop = await SenderUnionInfo.resolve_union("UNIONTEST|modmove|2")
        await PhigrosBindInfo.create(union_id=drop.union_id, session_token="tok", username="mover")

        merged = await keep.merge_union(drop)

        # union_id 为模块表主键，改挂只能通过重建行完成，各列值须原样保留。
        moved = await PhigrosBindInfo.get_or_none(union_id=merged.union_id)
        if not moved or moved.username != "mover" or moved.session_token != "tok":
            return False
        return not await PhigrosBindInfo.exists(union_id=drop.union_id)

    except Exception:
        return False


async def _test_merge_union_module_conflict_keeps_self():
    """测试 merge_union - 模块表冲突默认保留发起方"""
    try:
        from modules.phigros.database.models import PhigrosBindInfo

        keep = await SenderUnionInfo.resolve_union("UNIONTEST|modkeep|1")
        drop = await SenderUnionInfo.resolve_union("UNIONTEST|modkeep|2")
        await PhigrosBindInfo.create(union_id=keep.union_id, session_token="mine", username="mine")
        await PhigrosBindInfo.create(union_id=drop.union_id, session_token="theirs", username="theirs")

        merged = await keep.merge_union(drop)

        row = await PhigrosBindInfo.get_or_none(union_id=merged.union_id)
        if not row or row.username != "mine":
            return False
        return not await PhigrosBindInfo.exists(union_id=drop.union_id)

    except Exception:
        return False


async def _test_merge_union_module_conflict_keeps_other():
    """测试 merge_union - keep_other_tables 指定时保留被并入方"""
    try:
        from modules.phigros.database.models import PhigrosBindInfo

        keep = await SenderUnionInfo.resolve_union("UNIONTEST|modother|1")
        drop = await SenderUnionInfo.resolve_union("UNIONTEST|modother|2")
        await PhigrosBindInfo.create(union_id=keep.union_id, session_token="mine", username="mine")
        await PhigrosBindInfo.create(union_id=drop.union_id, session_token="theirs", username="theirs")

        merged = await keep.merge_union(drop, {"module_phigros_bind_info"})

        row = await PhigrosBindInfo.get_or_none(union_id=merged.union_id)
        if not row or row.username != "theirs":
            return False
        return not await PhigrosBindInfo.exists(union_id=drop.union_id)

    except Exception:
        return False


async def _test_merge_target_union_moves_module_rows():
    """测试 merge_union - 场景侧模块表同样改挂 union"""
    try:
        from modules.wiki.database.models import WikiTargetInfo

        keep = await TargetUnionInfo.resolve_union("UNIONTEST|Group|wiki1")
        drop = await TargetUnionInfo.resolve_union("UNIONTEST|Group|wiki2")
        await WikiTargetInfo.create(
            union_id=drop.union_id,
            api_link="https://example.org/api.php",
            interwikis={"foo": "https://foo.example/"},
        )

        merged = await keep.merge_union(drop)

        moved = await WikiTargetInfo.get_or_none(union_id=merged.union_id)
        if not moved or moved.api_link != "https://example.org/api.php":
            return False
        # JSON 列在重建时可能被写为字符串，此处确认取回后仍为字典。
        if moved.interwikis != {"foo": "https://foo.example/"}:
            return False
        return not await WikiTargetInfo.exists(union_id=drop.union_id)

    except Exception:
        return False


async def _test_channel_id_increments_within_union():
    """测试消息通道 - 组内逐个递增，默认各占一号"""
    try:
        union = await TargetUnionInfo.resolve_union("UNIONTEST|Group|chan1")
        await union.bind_id("UNIONTEST|Group|chan2")
        await union.bind_id("UNIONTEST|Group|chan3")

        channels = await TargetUnionBind.list_channels(union.union_id)
        # 默认每个场景各占一号，即默认互不参与去重。
        return sorted(channels.values()) == [1, 2, 3]

    except Exception:
        return False


async def _test_reassign_channel_clears_peer_bots_atomically():
    """单场景换通道时一并清理双方互认记录，并可原子分配新通道号。"""
    first_id = "UNIONTEST|Group|rechannel-first"
    moved_id = "UNIONTEST|Group|rechannel-moved"
    untouched_id = "UNIONTEST|Group|rechannel-untouched"
    union = await TargetUnionInfo.resolve_union(first_id)
    await union.bind_id(moved_id)
    await union.bind_id(untouched_id)
    await union.link_peer_bots(
        {
            first_id: {moved_id: "UNIONTEST|rechannel-moved-bot"},
            moved_id: {first_id: "UNIONTEST|rechannel-first-bot"},
        }
    )

    if await TargetUnionInfo.reassign_channel(moved_id, 1) != 1:
        return False
    current = await TargetUnionInfo.get(union_id=union.union_id)
    channels = await TargetUnionBind.list_channels(union.union_id)
    if (
        channels != {first_id: 1, moved_id: 1, untouched_id: 3}
        or current.list_peer_bots(first_id)
        or current.list_peer_bots(moved_id)
    ):
        return False

    allocated = await TargetUnionInfo.reassign_channel(moved_id)
    channels = await TargetUnionBind.list_channels(union.union_id)
    return allocated == 4 and channels[moved_id] == 4


async def _test_reassign_channel_rolls_back_peer_cleanup_failure():
    """通道更新后的互认清理失败时，两部分都必须回滚。"""
    first_id = "UNIONTEST|Group|rechannel-rollback-first"
    moved_id = "UNIONTEST|Group|rechannel-rollback-moved"
    union = await TargetUnionInfo.resolve_union(first_id)
    await union.bind_id(moved_id)
    await union.link_peer_bots(
        {
            first_id: {moved_id: "UNIONTEST|rechannel-rollback-moved-bot"},
            moved_id: {first_id: "UNIONTEST|rechannel-rollback-first-bot"},
        }
    )
    before_data = (await TargetUnionInfo.get(union_id=union.union_id)).target_data

    with patch.object(
        TargetUnionInfo,
        "_forget_peer_bots_unlocked",
        new=AsyncMock(side_effect=RuntimeError("audit failure")),
    ):
        try:
            await TargetUnionInfo.reassign_channel(moved_id, 1)
        except RuntimeError:
            pass
        else:
            return False

    moved = await TargetUnionBind.get(target_id=moved_id)
    current = await TargetUnionInfo.get(union_id=union.union_id)
    return moved.channel_id == 2 and current.target_data == before_data


async def _test_unify_channels_moves_complete_equivalence_class():
    """并合通道须整体移动来源通道，不能把其中第三个平台入口拆开。"""
    anchor_id = "UNIONTEST|Group|unify-channel-anchor"
    source_id = "UNIONTEST|Group|unify-channel-source"
    source_peer_id = "UNIONTEST|Group|unify-channel-source-peer"
    unrelated_id = "UNIONTEST|Group|unify-channel-unrelated"
    union = await TargetUnionInfo.resolve_union(anchor_id)
    for target_id in (source_id, source_peer_id, unrelated_id):
        await union.bind_id(target_id)
    await TargetUnionInfo.reassign_channel(source_peer_id, 2)
    await union.link_peer_bots(
        {
            source_id: {source_peer_id: "UNIONTEST|unify-channel-source-peer-bot"},
            source_peer_id: {source_id: "UNIONTEST|unify-channel-source-bot"},
        }
    )

    channel_id = await TargetUnionInfo.unify_channels(anchor_id, source_id)
    channels = await TargetUnionBind.list_channels(union.union_id)
    current = await TargetUnionInfo.get(union_id=union.union_id)
    return (
        channel_id == 1
        and channels[anchor_id] == channels[source_id] == channels[source_peer_id] == 1
        and channels[unrelated_id] == 4
        and current.list_peer_bots(source_id) == ["UNIONTEST|unify-channel-source-peer-bot"]
        and current.list_peer_bots(source_peer_id) == ["UNIONTEST|unify-channel-source-bot"]
    )


async def _test_sender_merge_rolls_back_on_failure():
    """测试 merge_union - 中途异常时新组、映射、Captcha 引用和旧组数据全部回滚。"""
    from modules.captcha.database.models import CaptchaChallenge, CaptchaTrust
    from modules.captcha.service import verification_id

    first_id = "UNIONTEST|rollback|sender1"
    second_id = "UNIONTEST|rollback|sender2"
    first = await SenderUnionInfo.resolve_union(first_id)
    second = await SenderUnionInfo.resolve_union(second_id)
    target = await TargetUnionInfo.resolve_union("UNIONTEST|Group|rollback-sender-target")
    challenge = await CaptchaChallenge.create(
        challenge_id="rollback-sender-merge-challenge",
        target_union_id=target.union_id,
        sender_union_id=first.union_id,
        target_id="UNIONTEST|Group|rollback-sender-target",
        sender_id=first_id,
        token="rollback-sender-merge-token",
        answer=42,
        choices=[42],
        status="pending",
    )
    trust_id = verification_id(target.union_id, first.union_id)
    await CaptchaTrust.create(
        trust_id=trust_id,
        target_union_id=target.union_id,
        sender_union_id=first.union_id,
    )
    before_count = await SenderUnionInfo.all().count()

    with patch("core.database.models.rewrite_sender_union_refs", side_effect=RuntimeError("audit failure")):
        try:
            await first.merge_union(second)
        except RuntimeError:
            pass
        else:
            return False

    first_bind = await SenderUnionBind.get(sender_id=first_id)
    second_bind = await SenderUnionBind.get(sender_id=second_id)
    await challenge.refresh_from_db()
    return (
        await SenderUnionInfo.all().count() == before_count
        and await SenderUnionInfo.exists(union_id=first.union_id)
        and await SenderUnionInfo.exists(union_id=second.union_id)
        and first_bind.union_id == first.union_id
        and second_bind.union_id == second.union_id
        and challenge.sender_union_id == first.union_id
        and await CaptchaTrust.exists(trust_id=trust_id, sender_union_id=first.union_id)
    )


async def _test_target_merge_rolls_back_on_failure():
    """测试场景 merge_union - 显式引用迁移异常时不遗留新组或半迁移 Captcha 引用。"""
    from core.database.models import migrate_union_references
    from modules.captcha.database.models import CaptchaChallenge, CaptchaTrust
    from modules.captcha.service import verification_id

    first_id = "UNIONTEST|Group|rollback-target1"
    second_id = "UNIONTEST|Group|rollback-target2"
    first = await TargetUnionInfo.resolve_union(first_id)
    second = await TargetUnionInfo.resolve_union(second_id)
    sender = await SenderUnionInfo.resolve_union("UNIONTEST|rollback-target-sender")
    challenge = await CaptchaChallenge.create(
        challenge_id="rollback-target-merge-challenge",
        target_union_id=first.union_id,
        sender_union_id=sender.union_id,
        target_id=first_id,
        sender_id="UNIONTEST|rollback-target-sender",
        token="rollback-target-merge-token",
        answer=42,
        choices=[42],
        status="pending",
    )
    trust_id = verification_id(first.union_id, sender.union_id)
    await CaptchaTrust.create(
        trust_id=trust_id,
        target_union_id=first.union_id,
        sender_union_id=sender.union_id,
    )
    before_count = await TargetUnionInfo.all().count()

    async def migrate_then_fail(*args, **kwargs):
        await migrate_union_references(*args, **kwargs)
        raise RuntimeError("audit failure")

    with patch("core.database.models.migrate_union_references", side_effect=migrate_then_fail):
        try:
            await first.merge_union(second)
        except RuntimeError:
            pass
        else:
            return False

    first_bind = await TargetUnionBind.get(target_id=first_id)
    second_bind = await TargetUnionBind.get(target_id=second_id)
    await challenge.refresh_from_db()
    return (
        await TargetUnionInfo.all().count() == before_count
        and await TargetUnionInfo.exists(union_id=first.union_id)
        and await TargetUnionInfo.exists(union_id=second.union_id)
        and first_bind.union_id == first.union_id
        and second_bind.union_id == second.union_id
        and challenge.target_union_id == first.union_id
        and await CaptchaTrust.exists(trust_id=trust_id, target_union_id=first.union_id)
    )


async def _test_sender_unbind_rolls_back_on_failure():
    """显式引用迁移失败时，用户解绑的 Challenge、映射与新组须全部回滚。"""
    from modules.captcha.database.models import CaptchaChallenge

    kept_id = "UNIONTEST|rollback|unbind-sender-kept"
    split_id = "UNIONTEST|rollback|unbind-sender-split"
    union = await SenderUnionInfo.resolve_union(kept_id)
    await union.bind_id(split_id)
    target = await TargetUnionInfo.resolve_union("UNIONTEST|Group|rollback-unbind-sender-target")
    challenge = await CaptchaChallenge.create(
        challenge_id="rollback-unbind-sender-challenge",
        target_union_id=target.union_id,
        sender_union_id=union.union_id,
        target_id="UNIONTEST|Group|rollback-unbind-sender-target",
        sender_id=split_id,
        token="rollback-unbind-sender-token",
        answer=42,
        choices=[42],
        status="pending",
    )
    before_count = await SenderUnionInfo.all().count()

    original_handler = CaptchaChallenge.migrate_unbound_union_reference

    async def migrate_then_fail(*args):
        await original_handler(*args)
        raise RuntimeError("audit failure")

    handler = AsyncMock(side_effect=migrate_then_fail)
    with patch.object(CaptchaChallenge, "migrate_unbound_union_reference", new=handler):
        try:
            await union.unbind_id(split_id)
        except RuntimeError:
            pass
        else:
            return False

    split_bind = await SenderUnionBind.get(sender_id=split_id)
    await challenge.refresh_from_db()
    return (
        handler.await_count == 1
        and await SenderUnionInfo.all().count() == before_count
        and await SenderUnionInfo.exists(union_id=union.union_id)
        and split_bind.union_id == union.union_id
        and challenge.sender_union_id == union.union_id
        and sorted(await union.list_bound_ids()) == sorted([kept_id, split_id])
    )


async def _test_target_unbind_rolls_back_on_failure():
    """显式引用迁移失败时，场景解绑的 Challenge、通道、互认记录与新组须全部回滚。"""
    from modules.captcha.database.models import CaptchaChallenge

    kept_id = "UNIONTEST|Group|rollback-unbind-target-kept"
    split_id = "UNIONTEST|Group|rollback-unbind-target-split"
    union = await TargetUnionInfo.resolve_union(kept_id)
    await union.bind_id(split_id)
    await union.link_peer_bots(
        {
            kept_id: {split_id: "UNIONTEST|rollback-unbind-target-split-bot"},
            split_id: {kept_id: "UNIONTEST|rollback-unbind-target-kept-bot"},
        }
    )
    sender = await SenderUnionInfo.resolve_union("UNIONTEST|rollback-unbind-target-sender")
    challenge = await CaptchaChallenge.create(
        challenge_id="rollback-unbind-target-challenge",
        target_union_id=union.union_id,
        sender_union_id=sender.union_id,
        target_id=split_id,
        sender_id="UNIONTEST|rollback-unbind-target-sender",
        token="rollback-unbind-target-token",
        answer=42,
        choices=[42],
        status="pending",
    )
    before_count = await TargetUnionInfo.all().count()
    before_target_data = (await TargetUnionInfo.get(union_id=union.union_id)).target_data

    original_handler = CaptchaChallenge.migrate_unbound_union_reference

    async def migrate_then_fail(*args):
        await original_handler(*args)
        raise RuntimeError("audit failure")

    handler = AsyncMock(side_effect=migrate_then_fail)
    with patch.object(CaptchaChallenge, "migrate_unbound_union_reference", new=handler):
        try:
            await union.unbind_id(split_id)
        except RuntimeError:
            pass
        else:
            return False

    split_bind = await TargetUnionBind.get(target_id=split_id)
    await challenge.refresh_from_db()
    current = await TargetUnionInfo.get(union_id=union.union_id)
    return (
        handler.await_count == 1
        and await TargetUnionInfo.all().count() == before_count
        and await TargetUnionInfo.exists(union_id=union.union_id)
        and split_bind.union_id == union.union_id
        and split_bind.channel_id == 2
        and challenge.target_union_id == union.union_id
        and current.target_data == before_target_data
        and sorted(await union.list_bound_ids()) == sorted([kept_id, split_id])
    )


async def _test_channel_id_concurrent_bind_is_unique():
    """测试消息通道 - 同组并发绑定不同场景时仍为每个新入口分配不同通道。"""
    union = await TargetUnionInfo.resolve_union("UNIONTEST|Group|concurrent-channel-base")
    target_ids = [f"UNIONTEST|Group|concurrent-channel-{index}" for index in range(20)]
    results = await asyncio.gather(*(union.bind_id(target_id) for target_id in target_ids), return_exceptions=True)
    if any(isinstance(result, BaseException) or result is not True for result in results):
        return False

    channels = await TargetUnionBind.list_channels(union.union_id)
    return len(channels) == 21 and len(set(channels.values())) == 21


async def _test_merge_union_renumbers_channels():
    """测试消息通道 - 合并时并入方重新编号，不与自身一侧重号"""
    try:
        first = await TargetUnionInfo.resolve_union("UNIONTEST|Group|mix1")
        await first.bind_id("UNIONTEST|Group|mix2")
        second = await TargetUnionInfo.resolve_union("UNIONTEST|Group|mix3")
        await second.bind_id("UNIONTEST|Group|mix4")

        merged = await first.merge_union(second)
        channels = await TargetUnionBind.list_channels(merged.union_id)

        # 两侧均自 1 起编号，直接合表会使四个互不相关的场景被归为两条通道。
        if sorted(channels.values()) != [1, 2, 3, 4]:
            return False
        return channels["UNIONTEST|Group|mix1"] != channels["UNIONTEST|Group|mix3"]

    except Exception:
        return False


async def _test_unbind_id_splits_account():
    """测试 unbind_id - 拆出的账号数据归零，处罚状态予以保留"""
    try:
        union = await SenderUnionInfo.resolve_union("UNIONTEST|unbind|1")
        await union.bind_id("UNIONTEST|unbind|2")
        union.petal = 20
        union.warns = 2
        await union.save()

        new_union = await union.unbind_id("UNIONTEST|unbind|2")
        if not new_union or new_union.union_id == union.union_id:
            return False
        # 花瓣保留在原 union，警告次数随账号转移，避免通过解绑规避处罚。
        if new_union.petal != 0 or new_union.warns != 2:
            return False

        kept = await SenderUnionInfo.resolve_union("UNIONTEST|unbind|1")
        if kept.petal != 20 or kept.union_id != union.union_id:
            return False

        return await union.list_bound_ids() == ["UNIONTEST|unbind|1"]

    except Exception:
        return False


async def _test_unbind_id_rejects_last():
    """测试 unbind_id - 仅剩一个账号时拒绝解绑"""
    try:
        union = await SenderUnionInfo.resolve_union("UNIONTEST|last|1")
        return await union.unbind_id("UNIONTEST|last|1") is None

    except Exception:
        return False


async def _test_target_union_shares_modules():
    """测试场景 union - 绑定后模块开关互通"""
    try:
        first = await TargetUnionInfo.resolve_union("UNIONTEST|Group|mod1")
        await first.bind_id("UNIONTEST|Group|mod2")
        await first.config_module("uniontest_module")

        second = await TargetUnionInfo.resolve_union("UNIONTEST|Group|mod2")
        return "uniontest_module" in second.modules

    except Exception:
        return False


async def _test_target_id_list_expands_union():
    """测试 get_target_id_list_by_module - 推送展开为全部平台场景"""
    try:
        first = await TargetUnionInfo.resolve_union("UNIONTEST|Group|push1")
        await first.bind_id("UNIONTEST|Group|push2")
        await first.config_module("uniontest_push")

        ids = await TargetUnionInfo.get_target_id_list_by_module("uniontest_push")
        return sorted(i for i in ids if i.startswith("UNIONTEST|")) == [
            "UNIONTEST|Group|push1",
            "UNIONTEST|Group|push2",
        ]

    except Exception:
        return False


async def _test_subscription_module_alias_migration():
    """旧模块名订阅应匹配新主名，并在下次开关时惰性归一化。"""
    new_name = "__test-subscription-new"
    old_name = "__test_subscription_old"
    target_id = "UNIONTEST|Group|subscription-alias"
    test_module = Module.assign(
        module_name=new_name,
        alias=old_name,
        recommend_modules=None,
        developers=None,
    )
    try:
        ModulesManager.add_module(test_module, "test.py")
        ModulesManager.refresh_modules_aliases()
        target = await TargetUnionInfo.resolve_union(target_id)
        target.modules = [old_name]
        await target.save()

        ids = await TargetUnionInfo.get_target_id_list_by_module(new_name)
        session = await SessionInfo.assign(target_id, target_from="UNIONTEST", client_name="UNIONTEST")
        await session.refresh_info()
        if target_id not in ids or new_name not in session.enabled_modules:
            return False

        await target.config_module(new_name, True)
        if target.modules != [new_name]:
            return False

        target.modules = [old_name]
        await target.save()
        await target.config_module(new_name, False)
        return target.modules == []
    finally:
        ModulesManager.modules.pop(new_name, None)
        ModulesManager.modules_origin.pop(new_name, None)
        ModulesManager.refresh()


async def _test_list_ids_accepts_multiple():
    """测试 list_ids - 支持一次展开多个 union"""
    try:
        first = await TargetUnionInfo.resolve_union("UNIONTEST|Group|multi1")
        second = await TargetUnionInfo.resolve_union("UNIONTEST|Group|multi2")

        ids = await TargetUnionBind.list_ids([first.union_id, second.union_id])
        if sorted(ids) != ["UNIONTEST|Group|multi1", "UNIONTEST|Group|multi2"]:
            return False

        return await TargetUnionBind.filter(union_id=first.union_id).count() == 1

    except Exception:
        return False


async def _test_delete_sender_union_cleans_current_state():
    """删除用户 Union 时清理模块状态、权限引用和验证码，但保留历史统计。"""
    from modules.captcha.database.models import CaptchaChallenge, CaptchaTrust
    from modules.captcha.service import verification_id
    from modules.cytoid.database.models import CytoidBindInfo
    from modules.maimai.database.models import DivingProberBindInfo, LxnsProberBindInfo
    from modules.phigros.database.models import PhigrosBindInfo

    sender_id = "UNIONTEST|delete|sender"
    target_id = "UNIONTEST|Group|delete-sender-ref"
    sender = await SenderUnionInfo.resolve_union(sender_id)
    target = await TargetUnionInfo.resolve_union(target_id)
    target.custom_admins = [sender.union_id]
    target.banned_users = [sender.union_id]
    await target.save(update_fields=["custom_admins", "banned_users"])
    await CytoidBindInfo.create(union_id=sender.union_id, username="delete-me")
    await DivingProberBindInfo.create(union_id=sender.union_id, username="delete-me")
    await LxnsProberBindInfo.create(union_id=sender.union_id, friend_code="123456")
    await PhigrosBindInfo.create(union_id=sender.union_id, session_token="delete-me", username="delete-me")
    pair_id = verification_id(target.union_id, sender.union_id)
    await CaptchaTrust.create(
        trust_id=pair_id,
        target_union_id=target.union_id,
        sender_union_id=sender.union_id,
    )
    await CaptchaChallenge.create(
        challenge_id=pair_id,
        target_union_id=target.union_id,
        sender_union_id=sender.union_id,
        target_id=target_id,
        sender_id=sender_id,
        token="delete-sender-safe-token",
        answer=42,
        choices=[42],
        status="verified",
    )
    history = await AnalyticsData.create(
        module_name="union-delete",
        module_type="command",
        target_id=target_id,
        sender_id=sender_id,
        target_union_id=target.union_id,
        sender_union_id=sender.union_id,
        command="delete",
    )

    union_id = sender.union_id
    if not await sender.delete_union():
        return False
    await target.refresh_from_db()
    return (
        not await SenderUnionInfo.exists(union_id=union_id)
        and not await SenderUnionBind.exists(sender_id=sender_id)
        and not await CytoidBindInfo.exists(union_id=union_id)
        and not await DivingProberBindInfo.exists(union_id=union_id)
        and not await LxnsProberBindInfo.exists(union_id=union_id)
        and not await PhigrosBindInfo.exists(union_id=union_id)
        and union_id not in target.custom_admins
        and union_id not in target.banned_users
        and not await CaptchaTrust.exists(sender_union_id=union_id)
        and not await CaptchaChallenge.exists(sender_union_id=union_id)
        and await AnalyticsData.exists(id=history.id, sender_union_id=union_id)
    )


async def _test_delete_target_union_cleans_current_state():
    """删除场景 Union 时清理场景模块状态和验证码，但保留历史统计。"""
    from modules.captcha.database.models import CaptchaChallenge, CaptchaTrust
    from modules.captcha.service import verification_id
    from modules.wiki.database.models import WikiTargetInfo
    from modules.wikilog.database.models import WikiLogTargetSetInfo

    sender_id = "UNIONTEST|delete|target-sender"
    target_id = "UNIONTEST|Group|delete-target"
    sender = await SenderUnionInfo.resolve_union(sender_id)
    target = await TargetUnionInfo.resolve_union(target_id)
    await WikiTargetInfo.create(union_id=target.union_id, api_link="https://delete.example/api.php")
    await WikiLogTargetSetInfo.create(union_id=target.union_id, infos={"https://delete.example/api.php": {}})
    pair_id = verification_id(target.union_id, sender.union_id)
    await CaptchaTrust.create(
        trust_id=pair_id,
        target_union_id=target.union_id,
        sender_union_id=sender.union_id,
    )
    await CaptchaChallenge.create(
        challenge_id=pair_id,
        target_union_id=target.union_id,
        sender_union_id=sender.union_id,
        target_id=target_id,
        sender_id=sender_id,
        token="delete-target-safe-token",
        answer=42,
        choices=[42],
        status="error",
    )
    history = await AnalyticsData.create(
        module_name="union-delete",
        module_type="command",
        target_id=target_id,
        sender_id=sender_id,
        target_union_id=target.union_id,
        sender_union_id=sender.union_id,
        command="delete",
    )

    union_id = target.union_id
    if not await target.delete_union():
        return False
    return (
        not await TargetUnionInfo.exists(union_id=union_id)
        and not await TargetUnionBind.exists(target_id=target_id)
        and not await WikiTargetInfo.exists(union_id=union_id)
        and not await WikiLogTargetSetInfo.exists(union_id=union_id)
        and not await CaptchaTrust.exists(target_union_id=union_id)
        and not await CaptchaChallenge.exists(target_union_id=union_id)
        and await AnalyticsData.exists(id=history.id, target_union_id=union_id)
    )


async def _test_delete_union_rejects_active_captcha():
    """仍有平台限制待解除的验证码时，删除必须整体拒绝。"""
    from modules.captcha.database.models import CaptchaChallenge
    from modules.captcha.service import verification_id

    sender_id = "UNIONTEST|delete|active-captcha-sender"
    target_id = "UNIONTEST|Group|delete-active-captcha-target"
    sender = await SenderUnionInfo.resolve_union(sender_id)
    target = await TargetUnionInfo.resolve_union(target_id)
    challenge_id = verification_id(target.union_id, sender.union_id)
    await CaptchaChallenge.create(
        challenge_id=challenge_id,
        target_union_id=target.union_id,
        sender_union_id=sender.union_id,
        target_id=target_id,
        sender_id=sender_id,
        token="delete-active-captcha-token",
        answer=42,
        choices=[42],
        status="pending",
    )

    try:
        await sender.delete_union()
    except UnionDeleteBlocked:
        pass
    else:
        return False
    return (
        await SenderUnionInfo.exists(union_id=sender.union_id)
        and await SenderUnionBind.exists(sender_id=sender_id, union_id=sender.union_id)
        and await CaptchaChallenge.exists(challenge_id=challenge_id)
    )


async def _test_sender_concurrent_unbind_keeps_remaining_union_mapped():
    """三个账号并发拆出两个时，原 Union 仍须保留核心行和最后一条映射。"""
    kept_id = "UNIONTEST|concurrent-unbind|sender-kept"
    split_ids = [
        "UNIONTEST|concurrent-unbind|sender-split-1",
        "UNIONTEST|concurrent-unbind|sender-split-2",
    ]
    union = await SenderUnionInfo.resolve_union(kept_id)
    for sender_id in split_ids:
        if not await union.bind_id(sender_id):
            return False

    stale_instances = await asyncio.gather(*(SenderUnionInfo.get_by_sender_id(kept_id) for _ in split_ids))
    results = await asyncio.gather(
        *(instance.unbind_id(sender_id) for instance, sender_id in zip(stale_instances, split_ids, strict=True)),
        return_exceptions=True,
    )
    if any(isinstance(result, BaseException) or result is None for result in results):
        return False

    kept_binds = await SenderUnionBind.filter(union_id=union.union_id).values_list("sender_id", flat=True)
    split_binds = await SenderUnionBind.filter(sender_id__in=split_ids).values_list("union_id", flat=True)
    split_unions_exist = await asyncio.gather(*(SenderUnionInfo.exists(union_id=result.union_id) for result in results))
    return (
        await SenderUnionInfo.exists(union_id=union.union_id)
        and kept_binds == [kept_id]
        and len(set(split_binds)) == 2
        and all(split_unions_exist)
    )


async def _test_target_concurrent_unbind_keeps_remaining_union_mapped():
    """三个场景并发拆出两个时，原 Union 仍须保留核心行和最后一条映射。"""
    kept_id = "UNIONTEST|Group|concurrent-unbind-target-kept"
    split_ids = [
        "UNIONTEST|Group|concurrent-unbind-target-split-1",
        "UNIONTEST|Group|concurrent-unbind-target-split-2",
    ]
    union = await TargetUnionInfo.resolve_union(kept_id)
    for target_id in split_ids:
        if not await union.bind_id(target_id):
            return False

    stale_instances = await asyncio.gather(*(TargetUnionInfo.get_by_target_id(kept_id) for _ in split_ids))
    results = await asyncio.gather(
        *(instance.unbind_id(target_id) for instance, target_id in zip(stale_instances, split_ids, strict=True)),
        return_exceptions=True,
    )
    if any(isinstance(result, BaseException) or result is None for result in results):
        return False

    kept_binds = await TargetUnionBind.filter(union_id=union.union_id).values_list("target_id", flat=True)
    split_binds = await TargetUnionBind.filter(target_id__in=split_ids).values_list("union_id", "channel_id")
    split_unions_exist = await asyncio.gather(*(TargetUnionInfo.exists(union_id=result.union_id) for result in results))
    return (
        await TargetUnionInfo.exists(union_id=union.union_id)
        and kept_binds == [kept_id]
        and len({union_id for union_id, _ in split_binds}) == 2
        and all(channel_id == 1 for _, channel_id in split_binds)
        and all(split_unions_exist)
    )


async def _test_stale_scalar_updates_preserve_fresh_json():
    """旧实例的标量更新不得把后来写入的 JSON、警告次数或其它字段覆盖掉。"""
    sender_id = "UNIONTEST|stale-scalar|sender"
    target_id = "UNIONTEST|Group|stale-scalar-target"
    stale_sender = await SenderUnionInfo.resolve_union(sender_id)
    stale_target = await TargetUnionInfo.resolve_union(target_id)
    fresh_sender = await SenderUnionInfo.get_by_sender_id(sender_id)
    fresh_target = await TargetUnionInfo.get_by_target_id(target_id)

    await fresh_sender.edit_sender_data("fresh", {"value": 1})
    await fresh_sender.warn_user(3)
    await fresh_target.edit_target_data("fresh", {"value": 2})

    if not await stale_sender.switch_identity(trust=True):
        return False
    if not await stale_target.edit_attr("locale", "en_us"):
        return False

    sender = await SenderUnionInfo.get_by_sender_id(sender_id)
    target = await TargetUnionInfo.get_by_target_id(target_id)
    return (
        sender.trusted
        and not sender.blocked
        and sender.warns == 3
        and sender.sender_data == {"fresh": {"value": 1}}
        and target.locale == "en_us"
        and target.target_data == {"fresh": {"value": 2}}
    )


async def _test_stale_sender_cannot_mutate_deleted_union():
    """删除用户 Union 后，旧 ORM 实例的全部 mutation 入口都不得复活核心行或映射。"""
    sender_id = "UNIONTEST|stale-delete|sender"
    added_id = "UNIONTEST|stale-delete|sender-added"
    stale = await SenderUnionInfo.resolve_union(sender_id)
    fresh = await SenderUnionInfo.get_by_sender_id(sender_id)
    if not await fresh.delete_union():
        return False

    results = [
        await stale.edit_attr("blocked", True),
        await stale.switch_identity(trust=False),
        await stale.warn_user(),
        await stale.modify_petal(5),
        await stale.clear_petal(),
        await stale.edit_sender_data("stale", True),
        await stale.bind_id(added_id),
    ]
    return (
        results == [False] * len(results)
        and not await SenderUnionInfo.exists(union_id=stale.union_id)
        and not await SenderUnionBind.exists(sender_id__in=[sender_id, added_id])
    )


async def _test_stale_target_cannot_mutate_deleted_union():
    """删除场景 Union 后，旧 ORM 实例的全部 mutation 入口都不得复活核心行或映射。"""
    target_id = "UNIONTEST|Group|stale-delete-target"
    added_id = "UNIONTEST|Group|stale-delete-target-added"
    stale = await TargetUnionInfo.resolve_union(target_id)
    fresh = await TargetUnionInfo.get_by_target_id(target_id)
    if not await fresh.delete_union():
        return False

    results = [
        await stale.edit_attr("locale", "en_us"),
        await stale.switch_mute(),
        await stale.edit_target_data("stale", True),
        await stale.config_module("stale-module"),
        await stale.config_custom_admin("USID|STALE-ADMIN"),
        await stale.config_banned_user("USID|STALE-BANNED"),
        await stale.link_peer_bots({target_id: {added_id: "bot"}}),
        await stale.forget_peer_bots(target_id),
        await stale.bind_id(added_id),
    ]
    return (
        results == [False] * len(results)
        and not await TargetUnionInfo.exists(union_id=stale.union_id)
        and not await TargetUnionBind.exists(target_id__in=[target_id, added_id])
    )


async def _test_stale_sender_merge_ignores_deleted_side():
    """合并前一侧已被删除时，旧实例不得把该侧花瓣、权限和 JSON 复制进存活方。"""
    deleted_id = "UNIONTEST|stale-merge|sender-deleted"
    kept_id = "UNIONTEST|stale-merge|sender-kept"
    stale_deleted = await SenderUnionInfo.resolve_union(deleted_id)
    stale_deleted.petal = 99
    stale_deleted.superuser = True
    stale_deleted.sender_data = {"deleted": True}
    await stale_deleted.save()
    kept = await SenderUnionInfo.resolve_union(kept_id)
    kept.petal = 7
    kept.sender_data = {"kept": True}
    await kept.save()
    before_count = await SenderUnionInfo.all().count()

    fresh_deleted = await SenderUnionInfo.get_by_sender_id(deleted_id)
    if not await fresh_deleted.delete_union():
        return False
    if await stale_deleted.merge_union(kept) is not None:
        return False

    refreshed_kept = await SenderUnionInfo.get_by_sender_id(kept_id)
    return (
        await SenderUnionInfo.all().count() == before_count - 1
        and refreshed_kept.union_id == kept.union_id
        and refreshed_kept.petal == 7
        and not refreshed_kept.superuser
        and refreshed_kept.sender_data == {"kept": True}
    )


async def _test_stale_target_merge_ignores_deleted_side():
    """合并前一侧已被删除时，旧实例不得把该侧权限、模块和 JSON 复制进存活方。"""
    deleted_id = "UNIONTEST|Group|stale-merge-target-deleted"
    kept_id = "UNIONTEST|Group|stale-merge-target-kept"
    stale_deleted = await TargetUnionInfo.resolve_union(deleted_id)
    stale_deleted.modules = ["deleted-module"]
    stale_deleted.custom_admins = ["USID|DELETED-ADMIN"]
    stale_deleted.target_data = {"deleted": True}
    await stale_deleted.save()
    kept = await TargetUnionInfo.resolve_union(kept_id)
    kept.modules = ["kept-module"]
    kept.custom_admins = ["USID|KEPT-ADMIN"]
    kept.target_data = {"kept": True}
    await kept.save()
    before_count = await TargetUnionInfo.all().count()

    fresh_deleted = await TargetUnionInfo.get_by_target_id(deleted_id)
    if not await fresh_deleted.delete_union():
        return False
    if await stale_deleted.merge_union(kept) is not None:
        return False

    refreshed_kept = await TargetUnionInfo.get_by_target_id(kept_id)
    return (
        await TargetUnionInfo.all().count() == before_count - 1
        and refreshed_kept.union_id == kept.union_id
        and refreshed_kept.modules == ["kept-module"]
        and refreshed_kept.custom_admins == ["USID|KEPT-ADMIN"]
        and refreshed_kept.target_data == {"kept": True}
    )


async def _test_module_create_rechecks_union_after_resolve():
    """模块行创建前须重查核心 Union，不能信任 resolve_union 返回后的旧实例。"""
    from modules.cytoid.database.models import CytoidBindInfo
    from modules.wiki.database.models import WikiTargetInfo

    sender_id = "UNIONTEST|module-create-race|sender"
    target_id = "UNIONTEST|Group|module-create-race-target"
    stale_sender = await SenderUnionInfo.resolve_union(sender_id)
    stale_target = await TargetUnionInfo.resolve_union(target_id)

    await SenderUnionBind.filter(sender_id=sender_id).delete()
    await SenderUnionInfo.filter(union_id=stale_sender.union_id).delete()
    await TargetUnionBind.filter(target_id=target_id).delete()
    await TargetUnionInfo.filter(union_id=stale_target.union_id).delete()

    with patch.object(SenderUnionInfo, "resolve_union", new=AsyncMock(return_value=stale_sender)):
        sender_module = await CytoidBindInfo.get_by_sender_id(sender_id)
    with patch.object(TargetUnionInfo, "resolve_union", new=AsyncMock(return_value=stale_target)):
        target_module = await WikiTargetInfo.get_by_target_id(target_id)

    return (
        sender_module is None
        and target_module is None
        and not await CytoidBindInfo.exists(union_id=stale_sender.union_id)
        and not await WikiTargetInfo.exists(union_id=stale_target.union_id)
    )


async def _test_bind_models_reject_deleted_union():
    """直接调用模块绑定写入口时，已删除的用户 Union 不得留下悬空模块行。"""
    from modules.cytoid.database.models import CytoidBindInfo
    from modules.maimai.database.models import DivingProberBindInfo, LxnsProberBindInfo
    from modules.phigros.database.models import PhigrosBindInfo

    sender_id = "UNIONTEST|module-bind-deleted|sender"
    sender = await SenderUnionInfo.resolve_union(sender_id)
    union_id = sender.union_id
    if not await sender.delete_union():
        return False

    results = [
        await CytoidBindInfo.set_bind_info(union_id, "user"),
        await DivingProberBindInfo.set_bind_info(union_id, "user"),
        await LxnsProberBindInfo.set_bind_info(union_id, "123456"),
        await PhigrosBindInfo.set_bind_info(union_id, "a" * 25),
    ]
    return results == [False] * 4 and not any(
        [
            await CytoidBindInfo.exists(union_id=union_id),
            await DivingProberBindInfo.exists(union_id=union_id),
            await LxnsProberBindInfo.exists(union_id=union_id),
            await PhigrosBindInfo.exists(union_id=union_id),
        ]
    )


async def _test_wiki_mutations_use_fresh_row():
    """Wiki 的旧实例更新不同字段或 JSON 键时应合并最新值，删除后不得写回。"""
    from modules.wiki.database.models import WikiTargetInfo

    target_id = "UNIONTEST|Group|wiki-stale-mutation"
    target = await TargetUnionInfo.resolve_union(target_id)
    wiki = await WikiTargetInfo.get_by_target_id(target_id)
    first = await WikiTargetInfo.get(union_id=wiki.union_id)
    second = await WikiTargetInfo.get(union_id=wiki.union_id)

    if not await first.config_interwikis("first", "https://first.example/api.php"):
        return False
    if not await second.config_interwikis("second", "https://second.example/api.php"):
        return False
    if not await first.config_headers('{"Accept":"plain","Accept-Language":"localized"}'):
        return False
    if not await second.config_headers("Accept-Language", add=False):
        return False
    if not await second.config_prefix("wiki:"):
        return False

    refreshed = await WikiTargetInfo.get(union_id=wiki.union_id)
    preserved = (
        refreshed.interwikis
        == {
            "first": "https://first.example/api.php",
            "second": "https://second.example/api.php",
        }
        and refreshed.headers.get("Accept") == "plain"
        and "Accept-Language" not in refreshed.headers
        and refreshed.prefix == "wiki:"
    )
    if not preserved or not await target.delete_union():
        return False

    return not await second.config_prefix("stale:") and not await WikiTargetInfo.exists(union_id=wiki.union_id)


async def _test_wikilog_mutations_use_fresh_nested_data():
    """Wikilog 的旧实例修改不同 Wiki 和嵌套字段时不得互相覆盖，删除后不得复活。"""
    from modules.wikilog.database.models import WikiLogTargetSetInfo

    target_id = "UNIONTEST|Group|wikilog-stale-mutation"
    target = await TargetUnionInfo.resolve_union(target_id)
    records = await WikiLogTargetSetInfo.get_by_target_id(target_id)
    first = await WikiLogTargetSetInfo.get(union_id=records.union_id)
    second = await WikiLogTargetSetInfo.get(union_id=records.union_id)
    first_api = "https://first-log.example/api.php"
    second_api = "https://second-log.example/api.php"

    if not await first.conf_wiki(first_api, add=True):
        return False
    if not await second.conf_wiki(second_api, add=True):
        return False

    first = await WikiLogTargetSetInfo.get(union_id=records.union_id)
    second = await WikiLogTargetSetInfo.get(union_id=records.union_id)
    if not await first.set_filters(first_api, "AbuseLog", ["filter-a"]):
        return False
    if not await second.set_rcshow(first_api, ["bot", "minor"]):
        return False
    if not await first.set_use_bot(first_api, True):
        return False
    if not await second.set_keep_alive(first_api, True):
        return False

    refreshed = await WikiLogTargetSetInfo.get(union_id=records.union_id)
    first_info = refreshed.infos.get(first_api, {})
    preserved = (
        second_api in refreshed.infos
        and first_info.get("AbuseLog", {}).get("filters") == ["filter-a"]
        and first_info.get("RecentChanges", {}).get("rcshow") == ["bot", "minor"]
        and first_info.get("use_bot") is True
        and first_info.get("keep_alive") is True
    )
    if not preserved or not await target.delete_union():
        return False

    return not await second.conf_note(first_api, "stale") and not await WikiLogTargetSetInfo.exists(
        union_id=records.union_id
    )


async def _test_wiki_allowlist_matches_exact_authority():
    """Wiki 白名单只信任相同主机与端口，不得以域名子串命中。"""
    from modules.wiki.database.models import WikiAllowList

    allowed = "https://trusted-sub.example.test/api.php"
    await WikiAllowList.remove(allowed)
    if not await WikiAllowList.add(allowed):
        return False
    try:
        return (
            await WikiAllowList.check("https://TRUSTED-SUB.EXAMPLE.TEST./w/api.php")
            and not await WikiAllowList.check("https://example.test/api.php")
            and not await WikiAllowList.check("https://nottrusted-sub.example.test/api.php")
            and not await WikiAllowList.check("https://trusted-sub.example.test:8443/api.php")
        )
    finally:
        await WikiAllowList.remove(allowed)


@func_case
async def test_union(tester: Tester):
    """core.database.models: union 绑定测试"""
    await tester.test(_test_resolve_union_creates_bind, "resolve_union 建出 union 与映射测试")
    await tester.test(_test_resolve_union_concurrent_same_id, "resolve_union 同 ID 并发解析测试")
    await tester.test(_test_new_union_id_prefixed, "new_union_id 域前缀测试")
    await tester.test(_test_resolve_union_no_create, "resolve_union 不建行测试")
    await tester.test(_test_bind_id_shares_data, "bind_id 数据共享测试")
    await tester.test(_test_bind_id_rejects_other_union, "bind_id 拒绝跨 union 测试")
    await tester.test(_test_bind_id_concurrent_claim_returns_boolean, "bind_id 并发争用返回值测试")
    await tester.test(_test_counter_updates_are_atomic, "用户计数器并发增量测试")
    await tester.test(_test_json_updates_preserve_concurrent_keys, "Union JSON 并发更新测试")
    await tester.test(_test_permission_lists_preserve_concurrent_members, "场景权限列表并发更新测试")
    await tester.test(_test_block_applies_to_whole_union, "封禁作用于整组测试")
    await tester.test(_test_merge_keeps_block, "合并不稀释封禁测试")
    await tester.test(_test_unbind_keeps_block_and_binding, "解绑转移封禁且映射不断测试")
    await tester.test(_test_unblock_applies_to_whole_union, "解封作用于整组测试")
    await tester.test(_test_switch_identity_unblocks, "switch_identity 解封测试")
    await tester.test(_test_merge_union_creates_new_union, "merge_union 生成新组测试")
    await tester.test(_test_merge_union_merges_data, "merge_union 数据合并测试")
    await tester.test(_test_sender_merge_rolls_back_on_failure, "用户 union 合并失败回滚测试")
    await tester.test(_test_target_merge_rolls_back_on_failure, "场景 union 合并失败回滚测试")
    await tester.test(_test_sender_unbind_rolls_back_on_failure, "用户 union 解绑失败回滚测试")
    await tester.test(_test_target_unbind_rolls_back_on_failure, "场景 union 解绑失败回滚测试")
    await tester.test(_test_merge_union_rewrites_permission_refs, "merge_union 权限名单改写测试")
    await tester.test(_test_merge_union_moves_module_rows, "merge_union 模块表改挂测试")
    await tester.test(_test_merge_union_module_conflict_keeps_self, "merge_union 模块表冲突保留自身测试")
    await tester.test(_test_merge_union_module_conflict_keeps_other, "merge_union 模块表冲突保留对方测试")
    await tester.test(_test_merge_target_union_moves_module_rows, "merge_union 场景模块表改挂测试")
    await tester.test(_test_channel_id_increments_within_union, "消息通道组内递增测试")
    await tester.test(_test_channel_id_concurrent_bind_is_unique, "消息通道并发分配测试")
    await tester.test(_test_merge_union_renumbers_channels, "消息通道合并重新编号测试")
    await tester.test(_test_reassign_channel_clears_peer_bots_atomically, "消息通道变更原子清理互认测试")
    await tester.test(_test_reassign_channel_rolls_back_peer_cleanup_failure, "消息通道变更失败回滚测试")
    await tester.test(_test_unify_channels_moves_complete_equivalence_class, "消息通道整体并合测试")
    await tester.test(_test_unbind_id_splits_account, "unbind_id 拆分账号测试")
    await tester.test(_test_unbind_id_rejects_last, "unbind_id 拒绝解绑最后一个测试")
    await tester.test(_test_target_union_shares_modules, "场景 union 模块开关互通测试")
    await tester.test(_test_target_id_list_expands_union, "推送展开为全部平台场景测试")
    await tester.test(_test_subscription_module_alias_migration, "订阅模块旧主名无缝迁移测试")
    await tester.test(_test_list_ids_accepts_multiple, "list_ids 多 union 测试")
    await tester.test(_test_delete_sender_union_cleans_current_state, "删除用户 Union 清理当前状态测试")
    await tester.test(_test_delete_target_union_cleans_current_state, "删除场景 Union 清理当前状态测试")
    await tester.test(_test_delete_union_rejects_active_captcha, "活跃验证码阻止 Union 删除测试")
    await tester.test(
        _test_sender_concurrent_unbind_keeps_remaining_union_mapped,
        "用户 Union 并发解绑保留最后映射测试",
    )
    await tester.test(
        _test_target_concurrent_unbind_keeps_remaining_union_mapped,
        "场景 Union 并发解绑保留最后映射测试",
    )
    await tester.test(_test_stale_scalar_updates_preserve_fresh_json, "旧实例标量更新不覆盖新数据测试")
    await tester.test(_test_stale_sender_cannot_mutate_deleted_union, "旧用户实例不可复活已删除 Union 测试")
    await tester.test(_test_stale_target_cannot_mutate_deleted_union, "旧场景实例不可复活已删除 Union 测试")
    await tester.test(_test_stale_sender_merge_ignores_deleted_side, "旧用户实例不合并已删除一侧测试")
    await tester.test(_test_stale_target_merge_ignores_deleted_side, "旧场景实例不合并已删除一侧测试")
    await tester.test(_test_module_create_rechecks_union_after_resolve, "模块创建重查核心 Union 测试")
    await tester.test(_test_bind_models_reject_deleted_union, "模块绑定拒绝已删除 Union 测试")
    await tester.test(_test_wiki_mutations_use_fresh_row, "Wiki 旧实例定向更新测试")
    await tester.test(_test_wikilog_mutations_use_fresh_nested_data, "Wikilog 旧实例嵌套更新测试")
    await tester.test(_test_wiki_allowlist_matches_exact_authority, "Wiki 白名单精确域名测试")

    return tester
