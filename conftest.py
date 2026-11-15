"""pytest 的根级 conftest：铺设测试环境并注册 akari 的 pytest 插件。"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 导入 tester 即完成测试环境铺设，须早于任何 core.* 导入（说明见 core/constants/path.py）。
from tester import prepare_test_environment  # noqa: E402

prepare_test_environment()

pytest_plugins = ["core.tester.pytest_plugin"]
