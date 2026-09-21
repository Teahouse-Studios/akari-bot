"""modules.ai.setting 计费时间段单元测试。"""

from datetime import datetime, timezone
from unittest.mock import patch

from core.tester import func_case, Tester
from modules.ai import setting


def _test_time_rules_use_server_time():
    server_now = datetime(2024, 1, 2, 7, 30)
    utc_now = datetime(2024, 1, 2, 23, 30, tzinfo=timezone.utc)

    class FakeDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return server_now
            return utc_now

    llm = {
        "billing": {
            "type": "token",
            "price_in": 10,
            "price_cache_read": 20,
            "price_cache_write": 21,
            "price_out": 30,
            # 服务器本地时间 07:30 是周二，命中该时段；若按 UTC 23:30 判定则不命中。
            "time_rules": [
                {"time_range": "00:00-08:30", "week": [2], "price_in": 99},
            ],
        }
    }

    with patch.object(setting, "datetime", FakeDateTime):
        prices = setting.get_llm_billing(llm)

    assert prices["input_price"] == 99
    assert prices["cache_read_price"] == 20
    assert prices["cache_write_price"] == 21
    assert prices["output_price"] == 30
    return True


@func_case
async def test_ai_billing_time_rules(tester: Tester):
    """modules.ai.setting: LLM 计费时间段规则测试"""
    await tester.test(_test_time_rules_use_server_time, "计费时间段按服务器本地时间匹配测试")
    return tester
