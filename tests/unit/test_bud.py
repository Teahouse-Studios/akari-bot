"""core.utils.bud 单元测试 - 花苞（拼手气红包）系统。"""

from core.builtins.message.chain import MessageChain
from core.builtins.session.info import SessionInfo
from core.tester import func_case, Tester
from core.tester.mock.factory import TestDataFactory
from core.tester.mock.session import MockMessageSession


async def _test_split_amount_conservation():
    """split_amount - 总额守恒且份数正确"""
    try:
        from core.utils.bud import split_amount

        for total, count in [(100, 5), (10, 10), (1, 1), (999, 3)]:
            shares = split_amount(total, count)
            if len(shares) != count:
                return False
            if sum(shares) != total:
                return False
        return True
    except Exception:
        return False


async def _test_split_amount_minimum():
    """split_amount - 每份至少 1 片"""
    try:
        from core.utils.bud import split_amount

        for _ in range(200):
            shares = split_amount(50, 8)
            if any(s < 1 for s in shares):
                return False
        return True
    except Exception:
        return False


async def _test_split_amount_avoids_extreme_small_shares():
    """split_amount - 余量充足时避免拆出 1 片"""
    try:
        from core.utils.bud import split_amount

        for _ in range(200):
            shares = split_amount(50, 8)
            if min(shares) < 3:
                return False
        return True
    except Exception:
        return False


async def _test_split_amount_invalid():
    """split_amount - 非法参数抛异常"""
    try:
        from core.utils.bud import split_amount

        for total, count in [(0, 1), (5, 6), (3, 0)]:
            try:
                split_amount(total, count)
                return False
            except ValueError:
                continue
        return True
    except Exception:
        return False


async def _test_generate_bud_id():
    """generate_bud_id - 非空且不与已有 ID 冲突"""
    try:
        from core.utils.bud import generate_bud_id

        existing = {"abc12345", "xyz98765"}
        bud_id = generate_bud_id(existing)
        return bool(bud_id) and bud_id not in existing
    except Exception:
        return False


async def _test_bud_ttl_24h():
    """BUD_TTL_SECONDS - 花苞有效期为 24 小时"""
    try:
        from core.utils.bud import BUD_TTL_SECONDS

        return BUD_TTL_SECONDS == 24 * 60 * 60
    except Exception:
        return False


async def _test_bud_refund_on_expiry():
    """过期花苞未领取部分退回发送者"""
    try:
        from core.database.models import SenderUnionInfo
        from core.utils.bud import BUD_STORE_KEY, BUD_STORE_SCOPE, claim_bud, create_bud, find_bud
        from core.utils.storedata import get_stored_list, update_stored_list

        sender = await TestDataFactory.ensure_sender(sender_id="TEST|0", petal=0)
        msg = MockMessageSession("~test")
        await msg.async_init("~test")

        bud = await create_bud("TEST|0", sender.union_id, 100, 5, "refundcode")
        if bud is None:
            return False

        await TestDataFactory.ensure_sender(sender_id="TEST|1", petal=0)
        msg2 = MockMessageSession("~test")
        msg2.session_info = await SessionInfo.assign(
            target_id="TEST|Console|0",
            client_name="TEST",
            target_from="TEST",
            sender_id="TEST|1",
            sender_from="TEST",
            sender_name="TEST",
            messages=MessageChain.assign("~test"),
        )
        status, _, amount = await claim_bud(msg2, "refundcode")
        if status != "success":
            return False

        # 人为将花苞创建时间前移 25 小时，使其过期
        buds = await get_stored_list(BUD_STORE_SCOPE, BUD_STORE_KEY) or []
        for b in buds:
            if b.get("id") == bud["id"]:
                b["created"] -= 25 * 3600
        await update_stored_list(BUD_STORE_SCOPE, BUD_STORE_KEY, buds)

        # 触发清理与退款
        await find_bud(bud["id"])

        refreshed = await SenderUnionInfo.get(union_id=sender.union_id)
        # 发送者未领取的部分（100 - amount）应退回
        return refreshed.petal == 100 - amount
    except Exception:
        return False


@func_case
async def test_bud(tester: Tester):
    """core.utils.bud: 花苞系统测试"""
    await tester.test(_test_split_amount_conservation, "split_amount 总额守恒测试")
    await tester.test(_test_split_amount_minimum, "split_amount 每份至少 1 片测试")
    await tester.test(_test_split_amount_avoids_extreme_small_shares, "split_amount 避免极端小额测试")
    await tester.test(_test_split_amount_invalid, "split_amount 非法参数测试")
    await tester.test(_test_generate_bud_id, "generate_bud_id 唯一性测试")
    await tester.test(_test_bud_ttl_24h, "花苞有效期 24 小时测试")
    await tester.test(_test_bud_refund_on_expiry, "过期花苞退款测试")

    return tester
