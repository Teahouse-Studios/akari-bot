"""pytest 适配层的根级 conftest。"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 导入 tester 即完成测试配置铺设，必须早于任何 core.* 导入（说明见 core/constants/path.py）。
from tester import test_config_path  # noqa: E402,F401

import pytest  # noqa: E402

from core.tester.mock.database import close_db, init_db  # noqa: E402
from core.tester.mock.loader import load_modules  # noqa: E402
from core.tester.mock.random import Random  # noqa: E402
from core.tester.pytest_plugin import (  # noqa: E402
    PytestTester,
    close_session_loop,
    make_item,
    run_in_session_loop,
)


def pytest_pycollect_makeitem(collector, name, obj):
    return make_item(collector, name, obj)


def pytest_sessionfinish(session, exitstatus):
    close_session_loop()


@pytest.fixture
def tester():
    """纯 pytest 风格用例的运行器。"""
    run_in_session_loop(close_db())
    run_in_session_loop(init_db())
    run_in_session_loop(load_modules(show_logs=False, monkey_patches={"Random": Random()}))
    yield PytestTester("pytest")
    run_in_session_loop(close_db())
