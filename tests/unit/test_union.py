"""core.database.models 单元测试 - union 绑定（需要数据库）。"""

from core.database.models import (
    SenderUnionInfo,
    SenderUnionBind,
    TargetUnionInfo,
    TargetUnionBind,
)
from core.tester import func_case, Tester


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


@func_case
async def test_union(tester: Tester):
    """core.database.models: union 绑定测试"""
    await tester.test(_test_resolve_union_creates_bind, "resolve_union 建出 union 与映射测试")
    await tester.test(_test_new_union_id_prefixed, "new_union_id 域前缀测试")
    await tester.test(_test_resolve_union_no_create, "resolve_union 不建行测试")
    await tester.test(_test_bind_id_shares_data, "bind_id 数据共享测试")
    await tester.test(_test_bind_id_rejects_other_union, "bind_id 拒绝跨 union 测试")
    await tester.test(_test_block_applies_to_whole_union, "封禁作用于整组测试")
    await tester.test(_test_merge_keeps_block, "合并不稀释封禁测试")
    await tester.test(_test_unbind_keeps_block_and_binding, "解绑转移封禁且映射不断测试")
    await tester.test(_test_unblock_applies_to_whole_union, "解封作用于整组测试")
    await tester.test(_test_switch_identity_unblocks, "switch_identity 解封测试")
    await tester.test(_test_merge_union_creates_new_union, "merge_union 生成新组测试")
    await tester.test(_test_merge_union_merges_data, "merge_union 数据合并测试")
    await tester.test(_test_merge_union_rewrites_permission_refs, "merge_union 权限名单改写测试")
    await tester.test(_test_merge_union_moves_module_rows, "merge_union 模块表改挂测试")
    await tester.test(_test_merge_union_module_conflict_keeps_self, "merge_union 模块表冲突保留自身测试")
    await tester.test(_test_merge_union_module_conflict_keeps_other, "merge_union 模块表冲突保留对方测试")
    await tester.test(_test_merge_target_union_moves_module_rows, "merge_union 场景模块表改挂测试")
    await tester.test(_test_channel_id_increments_within_union, "消息通道组内递增测试")
    await tester.test(_test_merge_union_renumbers_channels, "消息通道合并重新编号测试")
    await tester.test(_test_unbind_id_splits_account, "unbind_id 拆分账号测试")
    await tester.test(_test_unbind_id_rejects_last, "unbind_id 拒绝解绑最后一个测试")
    await tester.test(_test_target_union_shares_modules, "场景 union 模块开关互通测试")
    await tester.test(_test_target_id_list_expands_union, "推送展开为全部平台场景测试")
    await tester.test(_test_list_ids_accepts_multiple, "list_ids 多 union 测试")

    return tester
