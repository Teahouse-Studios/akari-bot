"""配置模板扫描的单元测试。"""

import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
from contextlib import contextmanager
from pathlib import Path

from core.config import CFGManager
from core.config.scan import scan_config_templates
from core.constants.version import config_version
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


def _test_core_templates_are_grouped_into_domain_files():
    """核心模板按领域拆分后，应保留旧导入路径并登记到各自的 TOML 文件。"""
    from core.config.base import (
        CoreConfig as CompatibleCoreConfig,
        JobQueueConfig as CompatibleJobQueueConfig,
        S3Config as CompatibleS3Config,
        WebRenderConfig as CompatibleWebRenderConfig,
    )
    from core.config.core import CoreConfig
    from core.config.jobqueue import JobQueueConfig, JobQueueSecretConfig
    from core.config.s3 import S3Config
    from core.config.webrender import WebRenderConfig

    jobqueue_fields = JobQueueConfig.__config_fields__
    return (
        CompatibleCoreConfig is CoreConfig
        and CompatibleJobQueueConfig is JobQueueConfig
        and CompatibleS3Config is S3Config
        and CompatibleWebRenderConfig is WebRenderConfig
        and "jobqueue_backend" not in CoreConfig.__config_fields__
        and set(jobqueue_fields)
        == {
            "jobqueue_backend",
            "jobqueue_node_id",
            "jobqueue_websocket_url",
            "jobqueue_websocket_embedded_hub",
            "jobqueue_websocket_bind_host",
            "jobqueue_websocket_bind_port",
            "jobqueue_websocket_queue_size",
            "jobqueue_websocket_max_message_bytes",
            "jobqueue_websocket_command_timeout",
        }
        and all(field["table_name"] == "jobqueue" and not field["secret"] for field in jobqueue_fields.values())
        and JobQueueSecretConfig.__config_fields__["jobqueue_websocket_token"]["table_name"] == "jobqueue"
        and JobQueueSecretConfig.__config_fields__["jobqueue_websocket_token"]["secret"]
        and jobqueue_fields["jobqueue_backend"]["standalone_comment_keys"]
        == (
            "config.notes.jobqueue.backend.intro",
            "config.notes.jobqueue.backend.database",
            "config.notes.jobqueue.backend.websocket",
            "config.notes.jobqueue.backend.consistency",
        )
    )


def _test_fresh_process_generates_all_grouped_core_templates():
    """全新进程只导入扫描器时，也应生成所有领域配置文件与独立说明注释。"""
    tmp = Path(tempfile.mkdtemp(prefix="akari_cfg_grouped_"))
    try:
        current_config = MINIMAL_CONFIG.replace("config_version = 3", f"config_version = {config_version}")
        (tmp / "config.toml").write_text(current_config, encoding="utf-8")
        env = os.environ.copy()
        env["AKARI_CONFIG_PATH"] = str(tmp)
        env.pop("AKARI_CONFIG_READONLY", None)
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "from core.constants import all_locales_path, lang_list; "
                    "from core.i18n import build_locale_snapshot, connect_locale_snapshot; "
                    "build_locale_snapshot(list(lang_list.keys()), all_locales_path, 'akari-bot'); "
                    "connect_locale_snapshot('akari-bot'); "
                    "from core.config.scan import scan_config_templates; "
                    "raise SystemExit(bool(scan_config_templates()))"
                ),
            ],
            cwd=Path(__file__).resolve().parents[2],
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
            check=False,
        )
        with (tmp / "config.toml").open("rb") as config_file:
            core_values = tomllib.load(config_file)
        with (tmp / "jobqueue.toml").open("rb") as jobqueue_file:
            jobqueue_values = tomllib.load(jobqueue_file)
        with (tmp / "s3.toml").open("rb") as s3_file:
            s3_values = tomllib.load(s3_file)
        with (tmp / "webrender.toml").open("rb") as webrender_file:
            webrender_values = tomllib.load(webrender_file)
        jobqueue_text = (tmp / "jobqueue.toml").read_text(encoding="utf-8")
        intro = "# JobQueue 必须在 database 与 websocket 中选择一套完整后端。"
        database = "# database：无需额外部署 Hub"
        websocket = "# websocket：项目推荐选项。经 Hub 实时路由"
        consistency = "# 所有进程必须使用同一后端。"
        backend = 'jobqueue_backend = "websocket"'
        return (
            result.returncode == 0
            and not any(key.startswith("jobqueue_") for key in core_values["config"])
            and not any(key.startswith("jobqueue_") for key in core_values["secret"])
            and jobqueue_values["jobqueue"]["jobqueue_backend"] == "websocket"
            and "jobqueue_websocket_token" in jobqueue_values["jobqueue_secret"]
            and "s3_bucket" in s3_values["s3"]
            and "remote_web_render_url" in webrender_values["webrender"]
            and jobqueue_text.index(intro)
            < jobqueue_text.index(database)
            < jobqueue_text.index(websocket)
            < jobqueue_text.index(consistency)
            < jobqueue_text.index(backend)
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


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


def _test_standalone_comment_declaration_is_validated():
    """独立注释只能由非空 i18n 键元组关联至同一模板内已声明的字段。"""
    from core.config.decorator import on_config

    with _temp_config():
        try:

            @on_config("probe", standalone_comments={"missing": ("config.header.line.1",)})
            class UnknownFieldConfig:
                known: bool = True

            del UnknownFieldConfig
            return False
        except ValueError:
            pass

        try:

            @on_config("probe", standalone_comments={"known": ["config.header.line.1"]})
            class InvalidKeysConfig:
                known: bool = True

            del InvalidKeysConfig
            return False
        except TypeError:
            pass

        try:

            @on_config("probe", standalone_comments={"known": ()})
            class EmptyKeysConfig:
                known: bool = True

            del EmptyKeysConfig
            return False
        except TypeError:
            pass

        @on_config("probe", standalone_comments={"known": ("config.notes.not_found",)})
        class MissingLocaleConfig:
            known: bool = True

        return MissingLocaleConfig.known is True


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
    await tester.test(_test_core_templates_are_grouped_into_domain_files, "核心配置模板独立文件与兼容导入测试")
    await tester.test(_test_fresh_process_generates_all_grouped_core_templates, "全新进程生成领域模板测试")
    await tester.test(_test_scan_writes_template_fields, "可写进程中模板补写字段测试")
    await tester.test(_test_standalone_comment_declaration_is_validated, "独立配置注释声明校验测试")
    await tester.test(_test_scan_repairs_raw_i18n_comments, "原始 i18n 配置注释修复测试")
    await tester.test(_test_importing_daemon_does_not_load_config, "守护进程延迟导入配置系统测试")
    await tester.test(_test_legacy_slower_schedule_migrates_to_multiplier, "旧 slower_schedule 布尔值迁移测试")

    return tester
