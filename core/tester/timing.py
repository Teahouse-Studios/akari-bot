"""测试时限的伸缩系数。"""

import os


def _resolve_time_scale() -> float:
    raw = os.environ.get("AKARI_TEST_TIME_SCALE", "").strip()
    if raw:
        try:
            return max(1.0, float(raw))
        except ValueError:
            pass
    return 10.0 if os.environ.get("CI") == "1" else 1.0


TIME_SCALE = _resolve_time_scale()

__all__ = ["TIME_SCALE"]
