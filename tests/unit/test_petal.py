"""core.utils.petal 单元测试 - 花瓣系统（需要数据库/配置）。"""

from datetime import timedelta

from core.config.base import CoreConfig
from core.tester import func_case, Tester, mock_config
from core.utils.timezone import core_now
from core.tester.mock.factory import TestDataFactory
from core.tester.mock.session import MockMessageSession


async def _test_cost_petal_insufficient_with_mock():
    try:
        from core.utils.petal import cost_petal

        await TestDataFactory.ensure_sender(petal=0)
        msg = MockMessageSession("~test")
        await msg.async_init("~test")

        with mock_config(CoreConfig, enable_petal=True):
            result = await cost_petal(msg, 100, send_prompt=False)
            if result is not False:
                return False

        return True
    except Exception:
        return False


async def _test_petal_session_balance_stays_in_sync():
    from core.database.models import SenderUnionInfo
    from core.utils.petal import gained_petal, lost_petal, cost_petal

    await TestDataFactory.ensure_sender(petal=0)
    msg = MockMessageSession("~test")
    await msg.async_init("~test")

    with mock_config(
        CoreConfig,
        enable_petal=True,
        enable_get_petal=True,
        petal_gained_limit=100,
        petal_lost_limit=100,
    ):
        await gained_petal(msg, 10)
        await cost_petal(msg, 3, send_prompt=False)
        await lost_petal(msg, 2)

    actual = await SenderUnionInfo.get(union_id=msg.session_info.sender_union_id)
    return msg.session_info.petal == actual.petal == 5


async def _test_sign_petal_once_per_day():
    from core.database.models import SenderUnionInfo, StoredData
    from core.utils.petal import sign_get_petal

    await TestDataFactory.ensure_sender(petal=0)
    msg = MockMessageSession("~test")
    await msg.async_init("~test")

    store_key = "Union|signedpetal"
    try:
        with mock_config(CoreConfig, enable_petal=True, petal_sign_min=5, petal_sign_max=5, petal_sign_rate=1.0):
            first = await sign_get_petal(msg)
            second = await sign_get_petal(msg)
            # 今日已签到返回 0，余额不再增加
            if first != 5 or second != 0:
                return False
            # 模拟跨过每日边界：把签到记录的过期时间改为过去
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


async def _test_sign_survives_core_offset_change():
    from core.database.models import StoredData
    from core.utils.petal import sign_get_petal

    await TestDataFactory.ensure_sender(petal=0)
    msg = MockMessageSession("~test")
    await msg.async_init("~test")
    union_id = msg.session_info.sender_union_id

    async def _clear_quota():
        stored = await StoredData.get_or_none(stored_key="Union|signedpetal")
        if not stored:
            return
        quota = dict(stored.value[0])
        quota.pop(union_id, None)
        stored.value = [quota]
        await stored.save(update_fields=["value"])

    await _clear_quota()
    try:
        with mock_config(
            CoreConfig,
            enable_petal=True,
            petal_sign_min=5,
            petal_sign_max=5,
            petal_sign_rate=1.0,
            timezone_offset="+8",
        ):
            first = await sign_get_petal(msg)
        with mock_config(
            CoreConfig,
            enable_petal=True,
            petal_sign_min=5,
            petal_sign_max=5,
            petal_sign_rate=1.0,
            timezone_offset="+14",
        ):
            second = await sign_get_petal(msg)
        # 改动核心时区不能改变已经写入的绝对到期时刻，因此不能重复签到。
        return first == 5 and second == 0
    finally:
        await _clear_quota()


async def _test_petal_reset_runs_once_per_cycle():
    from core.database.models import SenderUnionInfo, StoredData
    from core.utils.petal import PETAL_CYCLE_STORE_KEY, reset_petals_if_due

    sender = await TestDataFactory.ensure_sender(petal=10)

    try:
        await StoredData.filter(stored_key=PETAL_CYCLE_STORE_KEY).delete()
        with mock_config(CoreConfig, enable_petal=True, petal_keep_rate=0.2, petal_reset_crontab="0 0 1 * *"):
            first = await reset_petals_if_due()
            second = await reset_petals_if_due()
            # 模拟停机跨过周期边界：标记停留在过去的周期时补结算一次。
            stored = await StoredData.get(stored_key=PETAL_CYCLE_STORE_KEY)
            stored.value = [(core_now() - timedelta(days=1)).isoformat()]
            await stored.save(update_fields=["value"])
            third = await reset_petals_if_due()

        refreshed = await SenderUnionInfo.get(union_id=sender.union_id)
        return first >= 1 and second == 0 and third >= 1 and refreshed.petal == 0
    finally:
        await StoredData.filter(stored_key=PETAL_CYCLE_STORE_KEY).delete()


@func_case
async def test_petal(tester: Tester):
    """core.utils.petal: 花瓣系统测试"""
    await tester.test(_test_cost_petal_insufficient_with_mock, "cost_petal 花瓣不足 Mock 测试")
    await tester.test(_test_petal_session_balance_stays_in_sync, "花瓣变更后会话余额同步测试")
    await tester.test(_test_sign_petal_once_per_day, "签到每日仅一次且跨日重置测试")
    await tester.test(_test_sign_survives_core_offset_change, "核心时区变更不影响已写入的签到到期时刻")
    await tester.test(_test_petal_reset_runs_once_per_cycle, "花瓣周期结算每周期仅一次测试")

    return tester
