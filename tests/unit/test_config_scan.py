"""配置模板扫描的单元测试。"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

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


def _test_core_templates_are_grouped_into_domain_files():
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
            "jobqueue_websocket_mode",
            "jobqueue_websocket_url",
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
    from core.config.jobqueue import JobQueueConfig

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
                    "from core.config.jobqueue import bootstrap_jobqueue_config; "
                    "failed = scan_config_templates(); "
                    "bootstrap_jobqueue_config() if not failed else None; "
                    "raise SystemExit(bool(failed))"
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
        locale_path = Path(__file__).resolve().parents[2] / "core" / "locales" / "zh_cn.json"
        locale = json.loads(locale_path.read_text(encoding="utf-8"))
        comment_keys = JobQueueConfig.__config_fields__["jobqueue_backend"]["standalone_comment_keys"]
        jobqueue_lines = jobqueue_text.splitlines()
        expected_lines = [f"# {locale[key]}" for key in comment_keys]
        comment_positions = [jobqueue_lines.index(line) if line in jobqueue_lines else -1 for line in expected_lines]
        backend_line = 'jobqueue_backend = "websocket"'
        backend_positions = [i for i, line in enumerate(jobqueue_lines) if line.startswith(backend_line)]
        return (
            result.returncode == 0
            and not any(key.startswith("jobqueue_") for key in core_values["config"])
            and not any(key.startswith("jobqueue_") for key in core_values["secret"])
            and jobqueue_values["jobqueue"]["jobqueue_backend"] == "websocket"
            and UUID(jobqueue_values["jobqueue"]["jobqueue_node_id"]).version == 4
            and jobqueue_values["jobqueue"]["jobqueue_websocket_mode"] == "embedded"
            and len(jobqueue_values["jobqueue_secret"]["jobqueue_websocket_token"]) >= 43
            and "s3_bucket" in s3_values["s3"]
            and "remote_web_render_url" in webrender_values["webrender"]
            and all(position >= 0 for position in comment_positions)
            and len(set(comment_positions)) == len(comment_positions)
            and comment_positions == sorted(comment_positions)
            and len(backend_positions) == 1
            and comment_positions[-1] < backend_positions[0]
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _test_scan_covers_all_directories_with_config_templates():
    import bots
    import modules
    from core.config.scan import iter_config_template_modules

    listed = set(iter_config_template_modules())
    expected = set()
    for package in (bots, modules):
        package_path = Path(package.__path__[0])
        for entry in package_path.iterdir():
            if entry.is_dir() and not entry.name.startswith((".", "_")) and (entry / "config.py").is_file():
                expected.add(f"{package.__name__}.{entry.name}.config")
    # bots/milky 曾因缺少 __init__.py 而不被 pkgutil.iter_modules 收录，配置因而从未生成
    return bool(expected) and expected <= listed and "bots.milky.config" in listed


def _test_fresh_process_generates_bot_adapter_config():
    tmp = Path(tempfile.mkdtemp(prefix="akari_cfg_bot_"))
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
                    "failed = scan_config_templates(); "
                    # 与守护进程 spawn 出的平台进程一致：模板导入完毕后一律只读
                    "from core.config import CFGManager; "
                    "CFGManager.readonly = True; "
                    "from bots.milky.config import MilkyConfig, MilkySecretConfig; "
                    "print('MILKY', failed, MilkyConfig.enable, MilkyConfig.qq_host, "
                    "repr(MilkySecretConfig.qq_access_token))"
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
        written = (tmp / "bot_milky.toml").read_text(encoding="utf-8") if (tmp / "bot_milky.toml").is_file() else ""
        values = tomllib.loads(written) if written else {}
        summary = [line for line in result.stdout.splitlines() if line.startswith("MILKY ")]
        return (
            result.returncode == 0
            and summary == ["MILKY [] False http://127.0.0.1:8080 None"]
            and values.get("bot_milky", {}).get("enable") is False
            and values.get("bot_milky", {}).get("qq_host") == "http://127.0.0.1:8080"
            and values.get("bot_milky_secret", {}).get("qq_access_token") == "<Replace me with str value>"
            and "{I18N:" not in written
            and "使用 Milky 协议时，是否开启自身消息监听。" in written
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _test_jobqueue_bootstrap_persists_missing_values_once():
    from core.config.jobqueue import bootstrap_jobqueue_config

    generated_uuid = UUID("12345678-1234-4678-9234-567812345678")
    generated_token = "generated-jobqueue-token"
    with _temp_config() as tmp:
        CFGManager.edit_write("jobqueue_node_id", "  ", str, table_name="jobqueue")
        CFGManager.edit_write("jobqueue_websocket_token", "", str, secret=True, table_name="jobqueue")
        with (
            patch("core.config.jobqueue.uuid4", return_value=generated_uuid) as uuid_factory,
            patch("core.utils.random.SecureRandom.token_urlsafe", return_value=generated_token) as token_factory,
        ):
            first = bootstrap_jobqueue_config()
            second = bootstrap_jobqueue_config()

        with (tmp / "jobqueue.toml").open("rb") as jobqueue_file:
            values = tomllib.load(jobqueue_file)
        return (
            first == ("jobqueue_node_id", "jobqueue_websocket_token")
            and second == ()
            and uuid_factory.call_count == 1
            and token_factory.call_count == 1
            and values["jobqueue"]["jobqueue_node_id"] == str(generated_uuid)
            and values["jobqueue_secret"]["jobqueue_websocket_token"] == generated_token
        )


def _test_scan_writes_template_fields():
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
                    # 迁移后的 3 秒提示停顿不属于持久化行为；仅在隔离进程中跳过。
                    "from unittest.mock import patch\n"
                    "with patch('time.sleep'):\n"
                    "    from core.config import CFGManager\n"
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
        return result.returncode == 0 and output[-3:] == ["6", "3.0", "False"]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _test_legacy_allow_reload_base_is_removed():
    tmp = Path(tempfile.mkdtemp(prefix="akari_cfg_migrate_"))
    try:
        (tmp / "config.toml").write_text(
            'default_locale = "zh_cn"\nconfig_version = 5\n\n[config]\nallow_reload_base = true\n',
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
                    # 迁移后的 3 秒提示停顿不属于持久化行为；仅在隔离进程中跳过。
                    "from unittest.mock import patch\n"
                    "with patch('time.sleep'):\n"
                    "    from core.config import CFGManager\n"
                    "print(CFGManager.values['config']['config_version']); "
                    "print('allow_reload_base' in CFGManager.values['config']['config'])"
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
        return result.returncode == 0 and output[-2:] == ["6", "False"]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@func_case
async def test_config_scan(tester: Tester):
    """core.config.scan: 配置模板扫描测试"""
    await tester.test(_test_core_templates_are_grouped_into_domain_files, "核心配置模板独立文件与兼容导入测试")
    await tester.test(_test_fresh_process_generates_all_grouped_core_templates, "全新进程生成领域模板测试")
    await tester.test(_test_scan_covers_all_directories_with_config_templates, "平台与模块模板枚举一致性测试")
    await tester.test(_test_fresh_process_generates_bot_adapter_config, "全新进程生成平台适配器配置测试")
    await tester.test(_test_jobqueue_bootstrap_persists_missing_values_once, "JobQueue 身份与密钥持久化自举测试")
    await tester.test(_test_scan_writes_template_fields, "可写进程中模板补写字段测试")
    await tester.test(_test_standalone_comment_declaration_is_validated, "独立配置注释声明校验测试")
    await tester.test(_test_scan_repairs_raw_i18n_comments, "原始 i18n 配置注释修复测试")
    await tester.test(_test_importing_daemon_does_not_load_config, "守护进程延迟导入配置系统测试")
    await tester.test(_test_legacy_slower_schedule_migrates_to_multiplier, "旧 slower_schedule 布尔值迁移测试")
    await tester.test(_test_legacy_allow_reload_base_is_removed, "旧 allow_reload_base 配置项移除测试")

    return tester
