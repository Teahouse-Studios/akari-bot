"""core.loader 模块加载器单元测试。"""

from core.loader import ModulesManager
from core.tester import func_case, Tester
from core.types import Module
from core.types.module.component_meta import CommandMeta, RegexMeta


def _test_add_module():
    """ModulesManager.add_module: 添加模块"""
    try:
        test_module = Module.assign(
            module_name="__test_loader_mod_1", alias=None, recommend_modules=None, developers=None
        )
        ModulesManager.add_module(test_module, "test.py")
        result = "__test_loader_mod_1" in ModulesManager.modules
        ModulesManager.modules.pop("__test_loader_mod_1", None)
        ModulesManager.modules_origin.pop("__test_loader_mod_1", None)
        return result
    except Exception:
        return False


def _test_add_module_duplicate():
    """ModulesManager.add_module: 重复添加应抛出 ValueError"""
    try:
        test_module = Module.assign(
            module_name="__test_loader_mod_2", alias=None, recommend_modules=None, developers=None
        )
        ModulesManager.add_module(test_module, "test.py")
        try:
            duplicate = Module.assign(
                module_name="__test_loader_mod_2", alias=None, recommend_modules=None, developers=None
            )
            ModulesManager.add_module(duplicate, "test.py")
            ModulesManager.modules.pop("__test_loader_mod_2", None)
            ModulesManager.modules_origin.pop("__test_loader_mod_2", None)
            return False
        except ValueError:
            ModulesManager.modules.pop("__test_loader_mod_2", None)
            ModulesManager.modules_origin.pop("__test_loader_mod_2", None)
            return True
    except Exception:
        return False


def _test_remove_modules():
    """ModulesManager.remove_modules: 移除模块"""
    try:
        test_module = Module.assign(
            module_name="__test_loader_mod_3", alias=None, recommend_modules=None, developers=None
        )
        ModulesManager.add_module(test_module, "test.py")
        ModulesManager.remove_modules(["__test_loader_mod_3"])
        return "__test_loader_mod_3" not in ModulesManager.modules
    except Exception:
        return False


def _test_remove_nonexistent_module():
    """ModulesManager.remove_modules: 移除不存在的模块应抛出 ValueError"""
    try:
        ModulesManager.remove_modules(["__nonexistent_module_xyz_12345__"])
        return False
    except ValueError:
        return True
    except Exception:
        return False


def _test_bind_to_module_command():
    """ModulesManager.bind_to_module: 绑定 CommandMeta"""
    try:
        test_module = Module.assign(
            module_name="__test_loader_bind_1", alias=None, recommend_modules=None, developers=None
        )
        ModulesManager.add_module(test_module, "test.py")

        async def dummy_func(msg):
            pass

        meta = CommandMeta(function=dummy_func, command_template=[])
        ModulesManager.bind_to_module("__test_loader_bind_1", meta)
        result = len(ModulesManager.modules["__test_loader_bind_1"].command_list.set) == 1
        ModulesManager.modules.pop("__test_loader_bind_1", None)
        ModulesManager.modules_origin.pop("__test_loader_bind_1", None)
        return result
    except Exception:
        return False


def _test_bind_to_module_regex():
    """ModulesManager.bind_to_module: 绑定 RegexMeta"""
    try:
        test_module = Module.assign(
            module_name="__test_loader_bind_2", alias=None, recommend_modules=None, developers=None
        )
        ModulesManager.add_module(test_module, "test.py")

        async def dummy_func(msg):
            pass

        meta = RegexMeta(function=dummy_func, pattern=r"test")
        ModulesManager.bind_to_module("__test_loader_bind_2", meta)
        result = len(ModulesManager.modules["__test_loader_bind_2"].regex_list.set) == 1
        ModulesManager.modules.pop("__test_loader_bind_2", None)
        ModulesManager.modules_origin.pop("__test_loader_bind_2", None)
        return result
    except Exception:
        return False


def _test_bind_to_nonexistent_module():
    """ModulesManager.bind_to_module: 绑定到不存在的模块应静默忽略"""
    try:
        meta = CommandMeta(function=lambda m: None, command_template=[])
        ModulesManager.bind_to_module("__nonexistent_xyz__", meta)
        return True
    except Exception:
        return False


def _test_return_modules_list():
    """ModulesManager.return_modules_list: 返回所有模块"""
    try:
        test_module = Module.assign(
            module_name="__test_loader_list_1", alias=None, recommend_modules=None, developers=None
        )
        test_module._db_load = True
        ModulesManager.add_module(test_module, "test.py")
        modules = ModulesManager.return_modules_list()
        result = "__test_loader_list_1" in modules
        ModulesManager.modules.pop("__test_loader_list_1", None)
        ModulesManager.modules_origin.pop("__test_loader_list_1", None)
        return result
    except Exception:
        return False


def _test_return_modules_list_filter_platform():
    """ModulesManager.return_modules_list: 按平台过滤"""
    try:
        test_module = Module.assign(
            module_name="__test_loader_filter_1",
            alias=None,
            recommend_modules=None,
            developers=None,
            available_for=["QQ"],
        )
        test_module._db_load = True
        ModulesManager.add_module(test_module, "test.py")
        ModulesManager.refresh()

        qq_modules = ModulesManager.return_modules_list(target_from="QQ", client_name="QQ")
        discord_modules = ModulesManager.return_modules_list(target_from="Discord", client_name="Discord")

        qq_has = "__test_loader_filter_1" in qq_modules
        discord_has = "__test_loader_filter_1" in discord_modules

        ModulesManager.modules.pop("__test_loader_filter_1", None)
        ModulesManager.modules_origin.pop("__test_loader_filter_1", None)
        ModulesManager.refresh()

        return qq_has and not discord_has
    except Exception:
        return False


def _test_refresh_aliases():
    """ModulesManager.refresh_modules_aliases: 刷新别名"""
    try:
        test_module = Module.assign(
            module_name="__test_loader_alias_1",
            alias={"ta": "__test_loader_alias_1"},
            recommend_modules=None,
            developers=None,
        )
        ModulesManager.add_module(test_module, "test.py")
        ModulesManager.refresh_modules_aliases()
        result = ModulesManager.modules_aliases.get("ta") == "__test_loader_alias_1"
        ModulesManager.modules.pop("__test_loader_alias_1", None)
        ModulesManager.modules_origin.pop("__test_loader_alias_1", None)
        return result
    except Exception:
        return False


@func_case
async def test_loader(tester: Tester):
    """core.loader: 模块加载器测试"""
    await tester.test(_test_add_module, "ModulesManager.add_module 测试")
    await tester.test(_test_add_module_duplicate, "ModulesManager.add_module 重复测试")
    await tester.test(_test_remove_modules, "ModulesManager.remove_modules 测试")
    await tester.test(_test_remove_nonexistent_module, "ModulesManager.remove_modules 不存在测试")
    await tester.test(_test_bind_to_module_command, "ModulesManager.bind_to_module CommandMeta 测试")
    await tester.test(_test_bind_to_module_regex, "ModulesManager.bind_to_module RegexMeta 测试")
    await tester.test(_test_bind_to_nonexistent_module, "ModulesManager.bind_to_module 不存在模块测试")
    await tester.test(_test_return_modules_list, "ModulesManager.return_modules_list 测试")
    await tester.test(_test_return_modules_list_filter_platform, "ModulesManager.return_modules_list 平台过滤测试")
    await tester.test(_test_refresh_aliases, "ModulesManager.refresh_modules_aliases 测试")
    return tester
