"""core.utils.petal 单元测试 - 花瓣系统（需要数据库/配置）。"""

from unittest.mock import patch

from core.tester import func_case, Tester
from core.tester.mock.factory import TestDataFactory
from core.tester.mock.session import MockMessageSession


async def _test_petal_functions_no_throw():
    """测试花瓣函数 - 不抛出异常"""
    try:
        from core.utils.petal import gained_petal, lost_petal, cost_petal

        await TestDataFactory.setup_default_test_env()
        msg = MockMessageSession("~test")
        await msg.async_init("~test")

        await gained_petal(msg, 10)
        await lost_petal(msg, 10)
        await cost_petal(msg, 10, send_prompt=False)

        return True
    except Exception:
        return False


async def _test_cost_petal_returns_bool():
    """测试 cost_petal - 返回布尔值"""
    try:
        from core.utils.petal import cost_petal

        await TestDataFactory.setup_default_test_env()
        msg = MockMessageSession("~test")
        await msg.async_init("~test")

        result = await cost_petal(msg, 10, send_prompt=False)
        if not isinstance(result, bool):
            return False

        return True
    except Exception:
        return False


async def _test_gained_petal_with_mock():
    """测试 gained_petal - Mock Config 启用花瓣系统"""
    try:
        from core.utils.petal import gained_petal

        await TestDataFactory.setup_default_test_env()
        msg = MockMessageSession("~test")
        await msg.async_init("~test")

        class MockConfig:
            """替换 CoreConfig 的桩，仅提供被测代码读取的字段。"""

            enable_petal = True
            enable_get_petal = True
            petal_gained_limit = 100

        with patch("core.utils.petal.CoreConfig", MockConfig):
            result = await gained_petal(msg, 10)
            if result is None:
                return False

        return True
    except Exception:
        return False


async def _test_cost_petal_insufficient_with_mock():
    """测试 cost_petal - 花瓣不足时返回 False"""
    try:
        from core.utils.petal import cost_petal

        await TestDataFactory.ensure_sender(petal=0)
        msg = MockMessageSession("~test")
        await msg.async_init("~test")

        class MockConfig:
            """替换 CoreConfig 的桩，仅提供被测代码读取的字段。"""

            enable_petal = True

        with patch("core.utils.petal.CoreConfig", MockConfig):
            result = await cost_petal(msg, 100, send_prompt=False)
            if result is not False:
                return False

        return True
    except Exception:
        return False


async def _test_petal_session_balance_stays_in_sync():
    """测试花瓣变更后会话快照与实际余额一致。"""
    from core.database.models import SenderUnionInfo
    from core.utils.petal import gained_petal, lost_petal, cost_petal

    await TestDataFactory.ensure_sender(petal=0)
    msg = MockMessageSession("~test")
    await msg.async_init("~test")

    class MockConfig:
        enable_petal = True
        enable_get_petal = True
        petal_gained_limit = 100
        petal_lost_limit = 100

    with patch("core.utils.petal.CoreConfig", MockConfig):
        await gained_petal(msg, 10)
        await cost_petal(msg, 3, send_prompt=False)
        await lost_petal(msg, 2)

    actual = await SenderUnionInfo.get(union_id=msg.session_info.sender_union_id)
    return msg.session_info.petal == actual.petal == 5


async def _test_sign_petal_once_per_day():
    """测试 sign_get_petal - 同一 union 每日仅可签到一次，跨日（服务器 0 点）重置。"""
    from core.database.models import SenderUnionInfo, StoredData
    from core.utils.petal import sign_get_petal

    await TestDataFactory.ensure_sender(petal=0)
    msg = MockMessageSession("~test")
    await msg.async_init("~test")

    class MockConfig:
        """替换 CoreConfig 的桩，固定签到收益以便断言。"""

        enable_petal = True
        petal_sign_min = 5
        petal_sign_max = 5
        petal_sign_rate = 1.0

    store_key = "Union|signedpetal"
    try:
        with patch("core.utils.petal.CoreConfig", MockConfig):
            first = await sign_get_petal(msg)
            second = await sign_get_petal(msg)
            # 今日已签到返回 0，余额不再增加
            if first != 5 or second != 0:
                return False
            # 模拟跨过服务器 0 点：把签到记录的过期时间改为过去
            stored = await StoredData.get(stored_key=store_key)
            quota = dict(stored.value[0])
            quota[msg.session_info.sender_union_id]["expired"] = 0
            stored.value = [quota]
            await stored.save(update_fields=["value"])
            third = await sign_get_petal(msg)

        actual = await SenderUnionInfo.get(union_id=msg.session_info.sender_union_id)
        return third == 5 and actual.petal == 10
    finally:
        await StoredData.filter(stored_key=f"{store_key}").delete()


async def _test_petal_settlement_applies_rebate():
    """测试周期结算按返点比例保留余额。"""
    from core.database.models import SenderUnionInfo
    from core.utils.petal import settle_petals

    sender = await TestDataFactory.ensure_sender(petal=10)

    class MockConfig:
        enable_petal = True
        petal_rebate_rate = 0.2

    with patch("core.utils.petal.CoreConfig", MockConfig):
        await settle_petals()

    refreshed = await SenderUnionInfo.get(union_id=sender.union_id)
    return refreshed.petal == 2


@func_case
async def test_petal(tester: Tester):
    """core.utils.petal: 花瓣系统测试"""
    await tester.test(_test_petal_functions_no_throw, "花瓣函数不抛异常测试")
    await tester.test(_test_cost_petal_returns_bool, "cost_petal 返回布尔值测试")
    await tester.test(_test_gained_petal_with_mock, "gained_petal Mock Config 测试")
    await tester.test(_test_cost_petal_insufficient_with_mock, "cost_petal 花瓣不足 Mock 测试")
    await tester.test(_test_petal_session_balance_stays_in_sync, "花瓣变更后会话余额同步测试")
    await tester.test(_test_sign_petal_once_per_day, "签到每日仅一次且跨日重置测试")
    await tester.test(_test_petal_settlement_applies_rebate, "花瓣返点结算测试")

    return tester
