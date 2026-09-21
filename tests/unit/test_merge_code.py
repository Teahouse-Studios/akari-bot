"""modules.core.common_tools.merge 单元测试 - 迁移码的签发与消费。"""

from core.database.models import UNION_SCOPE_SENDER, UNION_SCOPE_TARGET, TargetUnionBind, TargetUnionInfo
from core.tester import func_case, Tester
from modules.core.common_tools import merge
from core.utils.union_merge import generate_code


async def _test_target_code_roundtrip():
    try:
        code = generate_code(
            merge._target_merge_codes,
            "UTID|AAA",
            "RETIRETEST|Group|1",
            {"is_private": False, "source_client": "RETIRETEST", "holder_target_id": "RETIRETEST|Group|1"},
        )
        scope, entry = merge._take_merge_code(code)
        return (
            scope == UNION_SCOPE_TARGET
            and entry["union_id"] == "UTID|AAA"
            and entry["is_private"] is False
            and entry["source_client"] == "RETIRETEST"
            and entry["holder_target_id"] == "RETIRETEST|Group|1"
        )

    except Exception:
        return False


async def _test_sender_code_roundtrip():
    try:
        code = generate_code(
            merge._sender_merge_codes,
            "USID|BBB",
            "RETIRETEST|Private|1",
            {
                "target_union_id": "UTID|BBB",
                "is_private": True,
                "source_client": "RETIRETEST",
                "holder_target_id": "RETIRETEST|Private|1",
            },
        )
        scope, entry = merge._take_merge_code(code)
        return (
            scope == UNION_SCOPE_SENDER
            and entry["union_id"] == "USID|BBB"
            and entry["target_union_id"] == "UTID|BBB"
            and entry["is_private"] is True
            and entry["holder_target_id"] == "RETIRETEST|Private|1"
        )

    except Exception:
        return False


async def _test_code_consumed_once():
    try:
        code = generate_code(merge._target_merge_codes, "UTID|CCC", "RETIRETEST|Group|2", {"is_private": False})
        merge._take_merge_code(code)
        return merge._take_merge_code(code) is None

    except Exception:
        return False


async def _test_invalid_code_returns_none():
    try:
        return merge._take_merge_code("ZZZZZZ") is None

    except Exception:
        return False


async def _test_bind_code_not_consumable():
    try:
        from modules.core.common_tools import bind

        code = generate_code(bind._sender_bind_codes, "USID|DDD", "QQ|1", {"is_private": True})
        taken = merge._take_merge_code(code)
        bind._take_code(code)  # 归还，避免影响其他用例
        return taken is None

    except Exception:
        return False


async def _test_unify_channel_merges_two_sessions():
    try:
        union = await TargetUnionInfo.resolve_union("MERGETEST|Group|ch1")
        await union.bind_id("MERGETEST2|Group|ch1")
        # 绑定时逐个递增编号，两者此刻不同号。
        before = await TargetUnionBind.list_channels(union.union_id)
        differed = before["MERGETEST|Group|ch1"] != before["MERGETEST2|Group|ch1"]

        await merge._unify_channel("MERGETEST|Group|ch1", "MERGETEST2|Group|ch1")

        after = await TargetUnionBind.list_channels(union.union_id)
        return differed and after["MERGETEST|Group|ch1"] == after["MERGETEST2|Group|ch1"]

    except Exception:
        return False


async def _test_unify_channel_missing_bind_is_safe():
    try:
        await merge._unify_channel("NOSUCH|Group|x", "NOSUCH|Group|y")
        return True

    except Exception:
        return False


async def _test_unify_channel_missing_initiator_reassigns_current():
    target_id = "MERGETEST|Group|missing-initiator"
    union = await TargetUnionInfo.resolve_union(target_id)
    await TargetUnionBind.filter(target_id=target_id).update(channel_id=7)
    try:
        channel_id = await merge._unify_channel("NOSUCH|Group|initiator", target_id)
        bind = await TargetUnionBind.get(target_id=target_id)
        return channel_id == 1 and bind.channel_id == 1
    finally:
        await union.delete_union()


@func_case
async def test_merge_code(tester: Tester):
    """modules.core.common_tools.merge: 迁移码签发与消费测试"""
    await tester.test(_test_target_code_roundtrip, "场景码往返测试")
    await tester.test(_test_sender_code_roundtrip, "账号码往返测试")
    await tester.test(_test_code_consumed_once, "一次性消费测试")
    await tester.test(_test_invalid_code_returns_none, "无效码测试")
    await tester.test(_test_bind_code_not_consumable, "与 bind 隔离测试")
    await tester.test(_test_unify_channel_merges_two_sessions, "通道统一测试")
    await tester.test(_test_unify_channel_missing_bind_is_safe, "缺绑定行兜底测试")
    await tester.test(_test_unify_channel_missing_initiator_reassigns_current, "缺发起方绑定时重分配当前通道测试")

    return tester
