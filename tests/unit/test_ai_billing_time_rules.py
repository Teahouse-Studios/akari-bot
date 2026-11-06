"""modules.ai.setting 计费时间段单元测试。"""

from datetime import datetime, timezone

from core.config.base import CoreConfig
from core.tester import func_case, Tester, mock_config
from modules.ai import setting


def _test_time_rules_use_core_offset():
    utc_now = datetime(2024, 1, 1, 23, 30, tzinfo=timezone.utc)

    llm = {
        "billing": {
            "type": "token",
            "price_in": 10,
            "price_cache_read": 20,
            "price_cache_write": 21,
            "price_out": 30,
            # 23:30 UTC 在核心默认时区 +8 下是周二 07:30，命中该时段；直接按 UTC 判定则不命中。
            "time_rules": [
                {"time_range": "00:00-08:30", "week": [2], "price_in": 99},
            ],
        }
    }

    with mock_config(CoreConfig, timezone_offset="+8"):
        prices = setting.get_llm_billing(llm, now=utc_now)

    assert prices["input_price"] == 99
    assert prices["cache_read_price"] == 20
    assert prices["cache_write_price"] == 21
    assert prices["output_price"] == 30
    return True


@func_case
async def test_ai_billing_time_rules(tester: Tester):
    """modules.ai.setting: LLM 计费时间段规则测试"""
    await tester.test(_test_time_rules_use_core_offset, "计费时间段按核心默认时区匹配测试")
    return tester
