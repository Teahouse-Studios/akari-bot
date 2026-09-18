"""测试时限的伸缩系数。

CI 托管 runner 上一次 SQLite 往返可能被线程调度拖到上百毫秒（本地约 0.1 毫秒），
按本地速度设定的固定 deadline 因此频繁误判超时。测试中等待其它任务或外部系统的
时限按本系数放大；生产代码的超时不受影响。
"""

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
