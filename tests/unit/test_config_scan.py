"""配置模板扫描的单元测试。"""

import os
import shutil
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

from core.config import CFGManager
from core.config.scan import scan_config_templates
from core.tester import func_case, Tester

MINIMAL_CONFIG = """# {I18N:config.header.line.1}
default_locale = "zh_cn"
config_version = 3

[config]
debug = false # {I18N:config.comments.config.debug}
legacy_probe = false # {I18N:config.comments.config.legacy_probe}

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
    """扫描所在的可写进程中，模板导入应将声明的字段及其本地化注释补入配置文件"""
    from core.config.decorator import on_config

    # 已被 tester 导入的模板不会再次执行 _process_class，故以此处声明的模板验证补写行为
    with _temp_config() as tmp:

        @on_config("config")
        class ScanProbeConfig:
            use_emote: bool = False

        del ScanProbeConfig
        written = (tmp / "config.toml").read_text(encoding="utf-8")
        return "use_emote = false # 是否使用表情资源。" in written


def _test_scan_repairs_raw_i18n_comments():
    """扫描应翻译有效标记并清除无法解析的过时标记，同时保留配置值"""
    with _temp_config() as tmp:
        if scan_config_templates():
            return False
        written = (tmp / "config.toml").read_text(encoding="utf-8")
        return (
            "# https://toml.io/cn/v1.0.0" in written
            and "debug = false # 是否开启调试模式，启用后会输出更多的日志信息。" in written
            and "legacy_probe = false" in written
            and "{I18N:" not in written
        )


def _test_importing_daemon_does_not_load_config():
    """守护进程模块的顶层导入不得提前触发 core.config 的导入期迁移"""
    env = os.environ.copy()
    result = subprocess.run(
        [sys.executable, "-c", "import sys; import bot; print('core.config' in sys.modules)"],
        cwd=Path(__file__).resolve().parents[2],
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )
    return result.returncode == 0 and result.stdout.strip().endswith("False")


def _test_legacy_slower_schedule_migrates_to_multiplier():
    """旧布尔开关应迁移为等价的计划任务间隔倍率。"""
    tmp = Path(tempfile.mkdtemp(prefix="akari_cfg_migrate_"))
    try:
        (tmp / "config.toml").write_text(
            'default_locale = "zh_cn"\nconfig_version = 4\n\n[config]\nslower_schedule = true\n',
            encoding="utf-8",
        )
        env = os.environ.copy()
        env["AKARI_CONFIG_PATH"] = str(tmp)
        env.pop("AKARI_CONFIG_READONLY", None)
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "from core.config import CFGManager; "
                    "print(CFGManager.values['config']['config_version']); "
                    "print(CFGManager.values['config']['config']['schedule_interval_multiplier']); "
                    "print('slower_schedule' in CFGManager.values['config']['config'])"
                ),
            ],
            cwd=Path(__file__).resolve().parents[2],
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=15,
            check=False,
        )
        output = result.stdout.splitlines()
        return result.returncode == 0 and output[-3:] == ["5", "3.0", "False"]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@func_case
async def test_config_scan(tester: Tester):
    """core.config.scan: 配置模板扫描测试"""
    await tester.test(_test_scan_reports_no_failure, "全部模板可加载测试")
    await tester.test(_test_scan_writes_template_fields, "可写进程中模板补写字段测试")
    await tester.test(_test_scan_repairs_raw_i18n_comments, "原始 i18n 配置注释修复测试")
    await tester.test(_test_importing_daemon_does_not_load_config, "守护进程延迟导入配置系统测试")
    await tester.test(_test_legacy_slower_schedule_migrates_to_multiplier, "旧 slower_schedule 布尔值迁移测试")

    return tester
