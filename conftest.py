"""pytest 适配层的根级 conftest。

自研框架的测试基座要求 ``AKARI_CONFIG_PATH`` 在任何 ``core.*`` 导入之前生效——``core.constants.path``
在导入期就会读取它（见 core/constants/path.py 中的说明）。因此这里先导入 tester 完成配置铺设，再让
pytest 收集测试模块；引导也不能放进 pytest 插件模块，因为 ``-p``/entry-point 插件会先于 conftest 导入。

用例的收集与执行见 core/tester/pytest_plugin.py，pytest 只是这套框架的第二个前端。
"""

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
    """``@func_case`` 入口交由框架执行，其余函数保持 pytest 默认收集行为。"""
    return make_item(collector, name, obj)


def pytest_sessionfinish(session, exitstatus):
    """收尾会话事件循环，避免遗留未关闭的循环与未完成的后台任务。"""
    close_session_loop()


@pytest.fixture
def tester():
    """
    纯 pytest 风格用例的运行器。

    基座按用例准备一次（重建内存数据库、加载模块），与 ``@func_case`` 入口一致；需要逐条目
    隔离时直接写 ``@func_case`` 入口即可。接口是同步的，异步操作在会话事件循环中执行，因此
    只能在同步测试函数里使用。
    """
    run_in_session_loop(close_db())
    run_in_session_loop(init_db())
    run_in_session_loop(load_modules(show_logs=False, monkey_patches={"Random": Random()}))
    yield PytestTester("pytest")
    run_in_session_loop(close_db())
