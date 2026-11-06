"""core.utils.petal 单元测试 - 花瓣系统（需要数据库/配置）。"""

import time
from datetime import datetime, timedelta

from core.config.base import CoreConfig
from core.tester import func_case, Tester, mock_config
from core.tester.mock.factory import TestDataFactory
from core.tester.mock.session import MockMessageSession
from core.utils.timezone import core_now


async def _set_target_offset(msg: MockMessageSession, offset: str) -> None:
    await msg.session_info.target_union_info.edit_target_data("timezone_offset", offset)
    await msg.session_info.refresh_info()


async def _delete_store(store_key: str) -> None:
    from core.database.models import StoredData

    await StoredData.filter(stored_key=store_key).delete()


async def _other_target_session(msg: MockMessageSession, target_id: str, offset: str):
    from core.builtins.session.info import SessionInfo
    from core.builtins.session.internal import MessageSession

    session_info = await SessionInfo.assign(
        target_id=target_id,
        target_from="TEST|Console",
        client_name="TEST",
        sender_id=msg.session_info.sender_id,
    )
    await session_info.target_union_info.edit_target_data("timezone_offset", offset)
    await session_info.refresh_info()
    return MessageSession(session_info=session_info)


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


async def _test_sign_is_shared_across_scenes():
    from core.utils.petal import sign_get_petal

    await TestDataFactory.ensure_sender(petal=0)
    msg = MockMessageSession("~test")
    await msg.async_init("~test")
    await _delete_store("Union|signedpetal")
    try:
        with mock_config(CoreConfig, enable_petal=True, petal_sign_min=5, petal_sign_max=5, petal_sign_rate=1.0):
            await _set_target_offset(msg, "+8")
            first = await sign_get_petal(msg)
            other = await _other_target_session(msg, "TEST|Console|petal_target_b", "+14")
            second = await sign_get_petal(other)
        # 同一用户在不同场景共用签到记录，不能因场景时区不同重复签到。
        return first == 5 and second == 0
    finally:
        await _delete_store("Union|signedpetal")


async def _test_sign_target_offset_change_rolls():
    from core.database.models import StoredData
    from core.utils.petal import sign_get_petal

    await TestDataFactory.ensure_sender(petal=0)
    msg = MockMessageSession("~test")
    await msg.async_init("~test")
    await _delete_store("Union|signedpetal")
    try:
        with mock_config(CoreConfig, enable_petal=True, petal_sign_min=5, petal_sign_max=5, petal_sign_rate=1.0):
            await _set_target_offset(msg, "+8")
            first = await sign_get_petal(msg)
            await _set_target_offset(msg, "+14")
            second = await sign_get_petal(msg)

            stored = await StoredData.get(stored_key="Union|signedpetal")
            quota = dict(stored.value[0])
            quota[msg.session_info.sender_union_id]["expired"] = 0
            stored.value = [quota]
            await stored.save(update_fields=["value"])
            third = await sign_get_petal(msg)

            stored = await StoredData.get(stored_key="Union|signedpetal")
            record = dict(stored.value[0])[msg.session_info.sender_union_id]
            rolled = 86000 < record["expired"] - time.time() <= 86500
            moved = record["offset"] == "+14"

            quota = dict(stored.value[0])
            quota[msg.session_info.sender_union_id]["expired"] = 0
            stored.value = [quota]
            await stored.save(update_fields=["value"])
            fourth = await sign_get_petal(msg)

            stored = await StoredData.get(stored_key="Union|signedpetal")
            stable_record = dict(stored.value[0])[msg.session_info.sender_union_id]
            stable_expiry = datetime.fromtimestamp(stable_record["expired"], tz=msg.session_info.tz)
            stable = (stable_expiry.hour, stable_expiry.minute, stable_expiry.second) == (0, 0, 0)

            quota = dict(stored.value[0])
            quota[msg.session_info.sender_union_id].pop("offset", None)
            quota[msg.session_info.sender_union_id]["expired"] = 0
            stored.value = [quota]
            await stored.save(update_fields=["value"])
            fifth = await sign_get_petal(msg)

            stored = await StoredData.get(stored_key="Union|signedpetal")
            legacy_record = dict(stored.value[0])[msg.session_info.sender_union_id]
            legacy_rolled = 86000 < legacy_record["expired"] - time.time() <= 86500

        return (
            first == 5
            and second == 0
            and third == 5
            and fourth == 5
            and fifth == 5
            and rolled
            and moved
            and stable
            and legacy_rolled
        )
    finally:
        await _delete_store("Union|signedpetal")


async def _test_gained_lost_limits_follow_target_offset():
    from core.database.models import StoredData
    from core.utils.petal import gained_petal, lost_petal

    await TestDataFactory.ensure_sender(petal=10)
    msg = MockMessageSession("~test")
    await msg.async_init("~test")
    keys = ("Union|gainedpetal", "Union|lostpetal")
    for key in keys:
        await _delete_store(key)
    try:
        with mock_config(
            CoreConfig,
            enable_petal=True,
            enable_get_petal=True,
            petal_gained_limit=5,
            petal_lost_limit=5,
        ):
            await _set_target_offset(msg, "+5:30")
            await gained_petal(msg, 1)
            await lost_petal(msg, 1)

        for key in keys:
            stored = await StoredData.get(stored_key=key)
            record = dict(stored.value[0])[msg.session_info.sender_union_id]
            if record["offset"] != "+5:30":
                return False
            expiry = datetime.fromtimestamp(record["expired"], tz=msg.session_info.tz)
            if (expiry.hour, expiry.minute, expiry.second) != (0, 0, 0):
                return False
        return True
    finally:
        for key in keys:
            await _delete_store(key)


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
    await tester.test(_test_sign_is_shared_across_scenes, "签到记录跨场景共享")
    await tester.test(_test_sign_target_offset_change_rolls, "改场景时区后首个周期按 24 小时滚动")
    await tester.test(_test_gained_lost_limits_follow_target_offset, "获取与失去上限按场景时区刷新")
    await tester.test(_test_petal_reset_runs_once_per_cycle, "花瓣周期结算每周期仅一次测试")

    return tester
