"""配置模板扫描的单元测试。"""

import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path

from core.config import CFGManager
from core.config.scan import scan_config_templates
from core.tester import func_case, Tester

MINIMAL_CONFIG = """default_locale = "zh_cn"
config_version = 3

[config]
debug = false

[secret]
db_path = "sqlite://database/save.db"
"""


@contextmanager
def _temp_config():
    """将 CFGManager 切换至一份空白的临时配置，退出时完整还原。

    :return: 临时配置目录的路径。
    """
    original_path = CFGManager.config_path
    original_values = CFGManager.values
    original_tss = CFGManager._tss
    original_file_list = CFGManager.config_file_list
    original_readonly = CFGManager.readonly

    tmp = Path(tempfile.mkdtemp(prefix="akari_cfg_scan_"))
    try:
        (tmp / "config.toml").write_text(MINIMAL_CONFIG, encoding="utf-8")
        CFGManager.switch_config_path(tmp)
        CFGManager.readonly = False
        yield tmp
    finally:
        CFGManager.readonly = original_readonly
        CFGManager.config_path = original_path
        CFGManager.values = original_values
        CFGManager._tss = original_tss
        CFGManager.config_file_list = original_file_list
        shutil.rmtree(tmp, ignore_errors=True)


def _test_scan_reports_no_failure():
    """仓库内全部配置模板都应能加载"""
    with _temp_config():
        return scan_config_templates() == []


def _test_scan_writes_template_fields():
    """扫描所在的可写进程中，模板导入应将声明的字段补入配置文件"""
    from core.config.decorator import on_config

    # 已被 tester 导入的模板不会再次执行 _process_class，故以此处声明的模板验证补写行为
    with _temp_config() as tmp:

        @on_config("scanprobe", "module")
        class ScanProbeConfig:
            scan_probe_value: int = 7

        del ScanProbeConfig
        written = tmp / "module_scanprobe.toml"
        return written.exists() and "scan_probe_value = 7" in written.read_text(encoding="utf-8")


@func_case
async def test_config_scan(tester: Tester):
    """core.config.scan: 配置模板扫描测试"""
    await tester.test(_test_scan_reports_no_failure, "全部模板可加载测试")
    await tester.test(_test_scan_writes_template_fields, "可写进程中模板补写字段测试")

    return tester
