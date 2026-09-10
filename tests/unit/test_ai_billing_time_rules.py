from datetime import datetime, timezone

from modules.ai import setting


def test_time_rules_use_server_time(monkeypatch):
    server_now = datetime(2024, 1, 2, 7, 30)
    utc_now = datetime(2024, 1, 2, 23, 30, tzinfo=timezone.utc)

    class FakeDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return server_now
            return utc_now

    monkeypatch.setattr(setting, "datetime", FakeDateTime)

    llm = {
        "billing": {
            "type": "token",
            "price_in": 10,
            "price_cache": 20,
            "price_out": 30,
            "time_rules": [
                {"time_range": "00:00-08:30", "week": [2], "price_in": 99},
            ],
        }
    }

    prices = setting.get_llm_billing(llm)

    assert prices["input_price"] == 99
    assert prices["cache_price"] == 20
    assert prices["output_price"] == 30
