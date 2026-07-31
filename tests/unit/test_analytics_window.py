"""modules.core.analytics 单元测试 - 统计时间窗口的时区处理（需要数据库）。"""

import warnings
from datetime import timedelta

from core.database.models import AnalyticsData
from core.tester import func_case, Tester
from modules.core.analytics import local_midnight


def _test_local_midnight_is_aware():
    """测试统计窗口 - 零点须带时区且时分秒微秒全为零"""
    try:
        midnight = local_midnight()
        return midnight.tzinfo is not None and (
            midnight.hour,
            midnight.minute,
            midnight.second,
            midnight.microsecond,
        ) == (0, 0, 0, 0)

    except Exception:
        return False


async def _test_window_emits_no_naive_warning():
    """测试统计窗口 - 查询不应触发 naive datetime 警告"""
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            old = local_midnight()
            await AnalyticsData.get_count_by_times(old + timedelta(days=1), old)
        # 不带时区的时间会被 Tortoise 当作 UTC，除了刷警告还会让窗口整体偏移一个时区差。
        return not [w for w in caught if "naive datetime" in str(w.message)]

    except Exception:
        return False


async def _test_window_counts_today_only():
    """测试统计窗口 - 今日窗口只计入今天的记录"""
    marker = "analytics_window_probe"
    try:
        old = local_midnight()
        new = old + timedelta(days=1)
        before = await AnalyticsData.get_count_by_times(new, old, marker)

        for offset in (timedelta(hours=1), timedelta(hours=12)):
            record = await AnalyticsData.create(
                module_name=marker, module_type="command", target_id="A|Group|1", command=f"~{marker}"
            )
            record.timestamp = old + offset
            await record.save(update_fields=["timestamp"])
        # 昨天与明天各一条，都不该被今日窗口计入
        for offset in (timedelta(hours=-1), timedelta(days=1, hours=1)):
            record = await AnalyticsData.create(
                module_name=marker, module_type="command", target_id="A|Group|1", command=f"~{marker}"
            )
            record.timestamp = old + offset
            await record.save(update_fields=["timestamp"])

        return await AnalyticsData.get_count_by_times(new, old, marker) - before == 2

    except Exception:
        return False
    finally:
        await AnalyticsData.filter(module_name=marker).delete()


@func_case
async def test_analytics_window(tester: Tester):
    """modules.core.analytics: 统计时间窗口测试"""
    await tester.test(_test_local_midnight_is_aware, "零点带时区测试")
    await tester.test(_test_window_emits_no_naive_warning, "无 naive datetime 警告测试")
    await tester.test(_test_window_counts_today_only, "今日窗口边界测试")

    return tester
