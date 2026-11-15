"""tests/unit 的公共夹具。"""

import pytest

from core.tester.pytest_plugin import prepare_runtime, run_in_session_loop


@pytest.fixture
def fresh_db():
    """在单个测试内重建内存数据库与模块注册表。"""
    run_in_session_loop(prepare_runtime())
