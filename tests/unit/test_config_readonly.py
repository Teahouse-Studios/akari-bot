"""配置只读语义与授权写入的单元测试。

配置的生成统一由 bot.py 的 pre_init() 完成，bot 与 server 子进程一律只读，
以免同一批配置项被多个进程重复补写。本组测试守住这一约束。
"""

import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path

from core.config import CFGManager
from core.constants.exceptions import ConfigOperationError
from core.tester import func_case, Tester

# 最小可用的配置文件内容，含表外顶层键、普通表与密钥表各一
MINIMAL_CONFIG = """default_locale = "zh_cn"
config_version = 3

[config]
debug = false

[secret]
db_path = "sqlite://database/save.db"
"""


@contextmanager
def _temp_config(readonly: bool):
    """将 CFGManager 切换至一份临时配置，退出时完整还原。

    :param readonly: 期间的只读标志。
    :return: 临时配置目录的路径。
    """
    original_path = CFGManager.config_path
    original_values = CFGManager.values
    original_tss = CFGManager._tss
    original_file_list = CFGManager.config_file_list
    original_readonly = CFGManager.readonly

    tmp = Path(tempfile.mkdtemp(prefix="akari_cfg_readonly_"))
    try:
        (tmp / "config.toml").write_text(MINIMAL_CONFIG, encoding="utf-8")
        CFGManager.switch_config_path(tmp)
        CFGManager.readonly = readonly
        yield tmp
    finally:
        CFGManager.readonly = original_readonly
        CFGManager.config_path = original_path
        CFGManager.values = original_values
        CFGManager._tss = original_tss
        CFGManager.config_file_list = original_file_list
        shutil.rmtree(tmp, ignore_errors=True)


def _test_readonly_write_raises():
    """只读时 write() 应抛 ConfigOperationError，且不改动内存中的配置"""
    with _temp_config(readonly=True):
        before = CFGManager.values["config"]["config"].get("debug")
        try:
            CFGManager.write("debug", True, bool, False, "config")
        except ConfigOperationError:
            return CFGManager.values["config"]["config"].get("debug") == before
        return False


def _test_readonly_delete_raises():
    """只读时 delete() 应抛 ConfigOperationError"""
    with _temp_config(readonly=True):
        try:
            CFGManager.delete("debug", "config")
        except ConfigOperationError:
            return "debug" in CFGManager.values["config"]["config"]
        return False


def _test_readonly_save_raises():
    """只读时 save() 应抛 ConfigOperationError"""
    with _temp_config(readonly=True):
        try:
            CFGManager.save()
        except ConfigOperationError:
            return True
        return False


def _test_readonly_get_missing_key_with_default_raises():
    """只读时读取缺失的键会触发回写默认值，应抛 ConfigOperationError"""
    with _temp_config(readonly=True):
        try:
            CFGManager.get("brand_new_key", "fallback", str, False, "config")
        except ConfigOperationError:
            return True
        return False


def _test_readonly_get_missing_key_without_default_returns_none():
    """只读时读取缺失且无默认值的键不涉及写入，应返回 None 而非抛出异常"""
    with _temp_config(readonly=True):
        return CFGManager.get("another_new_key", None, str, False, "config") is None


def _test_readonly_load_still_works():
    """只读时 load() 应正常执行，能读取磁盘上的新值"""
    with _temp_config(readonly=True) as tmp:
        path = tmp / "config.toml"
        path.write_text(path.read_text(encoding="utf-8").replace("debug = false", "debug = true"), encoding="utf-8")
        CFGManager.load()
        return CFGManager.values["config"]["config"]["debug"] is True


def _test_edit_write_succeeds_in_readonly():
    """edit_write() 在只读进程中应成功写入"""
    with _temp_config(readonly=True) as tmp:
        CFGManager.edit_write("debug", True, bool, False, "config")
        return "debug = true" in (tmp / "config.toml").read_text(encoding="utf-8")


def _test_edit_delete_succeeds_in_readonly():
    """edit_delete() 在只读进程中应成功删除并写入"""
    with _temp_config(readonly=True) as tmp:
        deleted = CFGManager.edit_delete("debug", "config")
        return deleted and "debug" not in (tmp / "config.toml").read_text(encoding="utf-8")


def _test_writable_scope_restores_readonly():
    """edit_* 结束后应恢复只读，计数归零"""
    with _temp_config(readonly=True):
        CFGManager.edit_write("debug", True, bool, False, "config")
        if CFGManager._allow_write_depth != 0:
            return False
        try:
            CFGManager.write("debug", False, bool, False, "config")
        except ConfigOperationError:
            return True
        return False


def _test_writable_process_can_write():
    """非只读进程中 write() 应正常执行"""
    with _temp_config(readonly=False) as tmp:
        CFGManager.write("debug", True, bool, False, "config")
        return "debug = true" in (tmp / "config.toml").read_text(encoding="utf-8")


def _test_readonly_template_registers_without_writing():
    """只读时导入配置模板应完成字段登记，且不产生任何写入"""
    from core.config.decorator import on_config

    with _temp_config(readonly=True) as tmp:
        before = (tmp / "config.toml").read_text(encoding="utf-8")

        @on_config("probe", "module")
        class ProbeConfig:
            probe_value: int = 42

        fields_registered = set(ProbeConfig.__config_fields__) == {"probe_value"}
        no_new_file = not (tmp / "module_probe.toml").exists()
        unchanged = (tmp / "config.toml").read_text(encoding="utf-8") == before
        return fields_registered and no_new_file and unchanged


@func_case
async def test_config_readonly(tester: Tester):
    """core.config: 配置只读语义测试"""
    await tester.test(_test_readonly_write_raises, "只读时 write 抛出异常测试")
    await tester.test(_test_readonly_delete_raises, "只读时 delete 抛出异常测试")
    await tester.test(_test_readonly_save_raises, "只读时 save 抛出异常测试")
    await tester.test(_test_readonly_get_missing_key_with_default_raises, "只读时读取缺失键且带默认值抛出异常测试")
    await tester.test(
        _test_readonly_get_missing_key_without_default_returns_none, "只读时读取缺失键且无默认值返回 None 测试"
    )
    await tester.test(_test_readonly_load_still_works, "只读时 load 正常测试")
    await tester.test(_test_edit_write_succeeds_in_readonly, "edit_write 授权写入测试")
    await tester.test(_test_edit_delete_succeeds_in_readonly, "edit_delete 授权删除测试")
    await tester.test(_test_writable_scope_restores_readonly, "授权作用域退出后恢复只读测试")
    await tester.test(_test_writable_process_can_write, "非只读进程写入正常测试")
    await tester.test(_test_readonly_template_registers_without_writing, "只读时模板登记不写入配置文件测试")

    return tester
