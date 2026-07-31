"""配置模板约束测试。

配置项此前被声明两次：一次在模板里，一次在实际取值的调用点。两处的键名、默认值、类型与表名
必须逐字抄对，抄错即造成同一配置项存在两个互不相同的默认值，取哪一个取决于配置文件里有没有这一项。
本组测试守住「模板是唯一定义处」这一约束，使抄写无从发生。
"""

import ast
import importlib
import pkgutil
from pathlib import Path

from core.config import CFGManager
from core.config.decorator import ConfigMeta
from core.logger import Logger
from core.tester import func_case, Tester

REPO_ROOT = Path(__file__).resolve().parents[2]

# Config() 的位置参数顺序，用于把位置实参还原成具名实参
CONFIG_POSITIONAL_ARGS = ["q", "default", "cfg_type", "secret", "table_name", "get_url", "_global", "_generate"]

# 扫描调用点时跳过的目录：core/config 是配置系统自身，tests 会直接调用 Config() 做单元测试
SCAN_EXCLUDED_DIRS = {".venv", "__pycache__", ".git", "node_modules", "assets", "tests"}


def _iter_templates():
    """遍历全部配置模板类，产出 (模块名, 模板类)。"""
    module_names = ["core.config.base"]
    import bots
    import modules

    for package in (bots, modules):
        for submodule in pkgutil.iter_modules(package.__path__):
            module_names.append(f"{package.__name__}.{submodule.name}.config")

    for module_name in module_names:
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError:
            continue
        for attr in vars(module).values():
            # 模板类由 ConfigMeta 创建，据此识别；再以 __module__ 排除转手导入进来的同一个类
            if isinstance(attr, ConfigMeta) and attr.__module__ == module_name:
                yield module_name, attr


def _iter_python_files():
    """遍历仓库内需要检查的 Python 源文件。"""
    for path in sorted(REPO_ROOT.rglob("*.py")):
        relative = path.relative_to(REPO_ROOT)
        if any(part in SCAN_EXCLUDED_DIRS for part in relative.parts):
            continue
        if relative.parts[:2] == ("core", "config"):
            continue
        yield path, relative


def _first_name_arg(node: ast.Call, func_name: str, keyword_name: str = "module_name") -> str | None:
    """取出 ``module()`` / ``on_module_config()`` / ``on_bot_config()`` 调用中的首个名称实参。

    :param node: 待检查的调用节点。
    :param func_name: 期望的被调函数名，不匹配时返回 None。
    :param keyword_name: 该名称写作关键字实参时所用的形参名。
    :return: 名称的字面量值，取不到时返回 None。
    """
    if not (isinstance(node.func, ast.Name) and node.func.id == func_name):
        return None
    candidate = node.args[0] if node.args else None
    if candidate is None:
        for keyword in node.keywords:
            if keyword.arg == keyword_name:
                candidate = keyword.value
                break
    if isinstance(candidate, ast.Constant) and isinstance(candidate.value, str):
        return candidate.value
    return None


def _config_call_kwargs(node: ast.Call) -> dict[str, ast.expr]:
    """把 Config() 调用的实参统一还原为具名形式。"""
    kwargs = {}
    for index, arg in enumerate(node.args):
        if index < len(CONFIG_POSITIONAL_ARGS):
            kwargs[CONFIG_POSITIONAL_ARGS[index]] = arg
    for keyword in node.keywords:
        kwargs[keyword.arg] = keyword.value
    return kwargs


def _test_template_reads_current_value():
    """模板类属性读到的应是配置文件中的当前值"""
    mismatched = []
    for module_name, template in _iter_templates():
        for field_name, get_kwargs in template.__config_fields__.items():
            if getattr(template, field_name) != CFGManager.get(**get_kwargs):
                mismatched.append(f"{module_name}.{template.__name__}.{field_name}")
    if mismatched:
        Logger.error(f"[ConfigTemplate] Fields whose value differs from CFGManager.get(): {mismatched}")
        return False
    return True


def _test_template_fields_not_shadowed():
    """模板类不得保留同名类属性，否则会遮蔽元类而读到静态默认值"""
    shadowed = []
    for module_name, template in _iter_templates():
        for field_name in template.__config_fields__:
            if field_name in template.__dict__:
                shadowed.append(f"{module_name}.{template.__name__}.{field_name}")
    if shadowed:
        Logger.error(f"[ConfigTemplate] Fields shadowed by a class attribute, reading the static default: {shadowed}")
        return False
    return True


def _test_template_covers_all_annotations():
    """模板的每个带注解字段都应完成登记，未登记的字段访问时会抛 AttributeError"""
    unregistered = []
    for module_name, template in _iter_templates():
        annotations = {k for k in getattr(template, "__annotations__", {}) if not k.startswith("__")}
        for field_name in annotations - set(template.__config_fields__):
            unregistered.append(f"{module_name}.{template.__name__}.{field_name}")
    if unregistered:
        Logger.error(f"[ConfigTemplate] Fields missing from __config_fields__: {unregistered}")
        return False
    return True


def _test_no_duplicate_declaration_at_call_sites():
    """调用点不得重复声明默认值或表名，配置项只能在模板里定义一次"""
    offenders = []
    for path, relative in _iter_python_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "Config"):
                continue
            kwargs = _config_call_kwargs(node)
            if "default" in kwargs or "table_name" in kwargs:
                offenders.append(f"{relative.as_posix()}:{node.lineno}  {ast.unparse(node)}")
    if offenders:
        Logger.error(
            f"[ConfigTemplate] Config() calls redeclaring a default or table name, "
            f"read the template class attribute instead: {offenders}"
        )
        return False
    return True


def _test_call_site_keys_not_declared_in_templates():
    """残留的 Config() 调用所读的键不应已由模板声明，否则存在两个定义处"""
    declared_keys = set()
    for _, template in _iter_templates():
        declared_keys.update(template.__config_fields__)

    offenders = []
    for path, relative in _iter_python_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "Config"):
                continue
            kwargs = _config_call_kwargs(node)
            key_node = kwargs.get("q")
            if not isinstance(key_node, ast.Constant) or not isinstance(key_node.value, str):
                continue
            if key_node.value in declared_keys:
                offenders.append(f"{relative.as_posix()}:{node.lineno}  {key_node.value}")
    if offenders:
        Logger.error(
            f"[ConfigTemplate] Config() calls reading a key already declared by a template, "
            f"read the template class attribute instead: {offenders}"
        )
        return False
    return True


def _test_module_config_table_matches_module_name():
    """on_module_config() 传入的模块名须与包内 module() 声明的一致，否则配置表名对不上"""
    mismatched = []
    for config_path in sorted((REPO_ROOT / "modules").glob("*/config.py")):
        package_dir = config_path.parent

        declared_module_names = set()
        for source_path in sorted(package_dir.rglob("*.py")):
            try:
                tree = ast.parse(source_path.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError):
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    declared = _first_name_arg(node, "module")
                    if declared:
                        declared_module_names.add(declared)

        for node in ast.walk(ast.parse(config_path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call):
                continue
            table_module_name = _first_name_arg(node, "on_module_config")
            if table_module_name and table_module_name not in declared_module_names:
                relative = config_path.relative_to(REPO_ROOT).as_posix()
                mismatched.append(f'{relative}:{node.lineno}  "{table_module_name}" 不在 {declared_module_names}')
    if mismatched:
        Logger.error(f"[ConfigTemplate] Module config table names not matching any module() declaration: {mismatched}")
        return False
    return True


def _test_bot_config_table_matches_directory_name():
    """on_bot_config() 传入的平台名须与 bots/ 下的目录名一致

    守护进程正是以 ``bot_<目录名>`` 的表名去查找该平台的 enable 配置的，对不上则该平台会被判定为禁用。
    """
    mismatched = []
    for config_path in sorted((REPO_ROOT / "bots").glob("*/config.py")):
        directory_name = config_path.parent.name
        for node in ast.walk(ast.parse(config_path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call):
                continue
            table_bot_name = _first_name_arg(node, "on_bot_config", "bot_name")
            if table_bot_name and table_bot_name != directory_name:
                relative = config_path.relative_to(REPO_ROOT).as_posix()
                mismatched.append(f'{relative}:{node.lineno}  "{table_bot_name}" != "{directory_name}"')
    if mismatched:
        Logger.error(f"[ConfigTemplate] Bot config table names not matching their directory name: {mismatched}")
        return False
    return True


def _test_no_unauthorized_config_write_call_sites():
    """core/config 与一次性脚本之外，不得直接调用 CFGManager 的写入方法"""
    forbidden_methods = {"write", "delete", "save"}
    offenders = []
    for path, relative in _iter_python_files():
        # core/scripts/ 下是离线运行的一次性脚本，不在 bot 进程内，允许直接写入
        if relative.parts[:2] == ("core", "scripts"):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in forbidden_methods
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "CFGManager"
            ):
                offenders.append(f"{relative.as_posix()}:{node.lineno}  {ast.unparse(node)}")
    if offenders:
        Logger.error(
            f"[ConfigTemplate] Calls bypassing the read-only guard, "
            f"use CFGManager.edit_write / edit_delete instead: {offenders}"
        )
        return False
    return True


@func_case
async def test_config_template(tester: Tester):
    """core.config: 配置模板约束测试"""
    await tester.test(_test_template_reads_current_value, "模板取值与配置文件一致测试")
    await tester.test(_test_template_fields_not_shadowed, "模板字段未被类属性遮蔽测试")
    await tester.test(_test_template_covers_all_annotations, "模板字段登记完整性测试")
    await tester.test(_test_no_duplicate_declaration_at_call_sites, "调用点无重复默认值声明测试")
    await tester.test(_test_call_site_keys_not_declared_in_templates, "调用点未重复读取模板键测试")
    await tester.test(_test_module_config_table_matches_module_name, "模块配置表名一致性测试")
    await tester.test(_test_bot_config_table_matches_directory_name, "平台配置表名一致性测试")
    await tester.test(_test_no_unauthorized_config_write_call_sites, "无未授权配置写入调用点测试")

    return tester
