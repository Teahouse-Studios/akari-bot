"""bots.web.api 单元测试 - 统计接口的时间窗口筛选（需要数据库）。"""

from datetime import datetime, timedelta, UTC
from unittest.mock import patch

import bots.web.api.api as web_api
from core.database.models import AnalyticsData
from core.tester import func_case, Tester

MARKER = "webui_analytics_probe"


async def _add_record(hours_ago: float) -> None:
    """
    写入一条指定时间的统计记录。timestamp 是 auto_now_add 字段，只能建好之后再改写。
    """
    record = await AnalyticsData.create(
        module_name=MARKER,
        module_type="command",
        target_id="WEBAPI|Group|1",
        sender_id="WEBAPI|1",
        command=f"~{MARKER}",
    )
    record.timestamp = datetime.now(UTC) - timedelta(hours=hours_ago)
    await record.save(update_fields=["timestamp"])


async def _test_analytics_counts_records_in_window():
    """测试统计接口 - 窗口内的记录应被计入而非始终返回空"""
    try:
        # 接口按整库统计，同批测试可能已写入其他记录，故以增量为准。
        with patch.object(web_api, "verify_jwt", lambda request: None):
            before = await web_api.get_analytics(None, days=1)

            await _add_record(hours_ago=1)
            await _add_record(hours_ago=20)
            # 落在一天窗口之外，不应被计入。
            await _add_record(hours_ago=30)

            after = await web_api.get_analytics(None, days=1)

        return (
            after["count"] - before["count"] == 2
            and len(after["data"]) - len(before["data"]) == 2
            and sum(1 for row in after["data"] if row["module_name"] == MARKER) == 2
        )

    except Exception:
        return False
    finally:
        await AnalyticsData.filter(module_name=MARKER).delete()


@func_case
async def test_webui_analytics(tester: Tester):
    """bots.web.api: 统计接口测试"""
    await tester.test(_test_analytics_counts_records_in_window, "统计接口时间窗口测试")

    return tester
