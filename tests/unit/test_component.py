"""core.component 组件注册系统单元测试。"""

from core.tester import func_case, Tester
from core.types import Module


def _test_bind_module_create():
    """Bind.Module: 创建实例"""
    try:
        from core.component import Bind

        bm = Bind.Module("test_bind_module")
        return bm.module_name == "test_bind_module"
    except Exception:
        return False


def _test_module_assign_basic():
    """Module.assign: 基本创建"""
    try:
        m = Module.assign(module_name="test_mod", alias=None, recommend_modules=None, developers=None)
        return m.module_name == "test_mod" and m.base is False and m.load is True
    except Exception:
        return False


def _test_module_assign_alias_str():
    """Module.assign: 字符串别名应转为字典"""
    try:
        m = Module.assign(module_name="test_mod", alias="tm", recommend_modules=None, developers=None)
        return m.alias == {"tm": "test_mod"}
    except Exception:
        return False


def _test_module_assign_alias_list():
    """Module.assign: 列表别名应转为字典"""
    try:
        m = Module.assign(module_name="test_mod", alias=["t1", "t2"], recommend_modules=None, developers=None)
        return m.alias == {"t1": "test_mod", "t2": "test_mod"}
    except Exception:
        return False


def _test_module_assign_alias_dict():
    """Module.assign: 字典别名保持不变"""
    try:
        m = Module.assign(module_name="test_mod", alias={"tm": "test_mod"}, recommend_modules=None, developers=None)
        return m.alias == {"tm": "test_mod"}
    except Exception:
        return False


def _test_module_assign_flags():
    """Module.assign: 标志位应正确设置"""
    try:
        m = Module.assign(
            module_name="test_mod",
            alias=None,
            recommend_modules=None,
            developers=None,
            base=True,
            hidden=True,
            required_admin=True,
            doc=True,
        )
        return m.base is True and m.hidden is True and m.required_admin is True and m.doc is True
    except Exception:
        return False


def _test_module_assign_available_for():
    """Module.assign: available_for 应转为列表"""
    try:
        m = Module.assign(
            module_name="test_mod", alias=None, recommend_modules=None, developers=None, available_for="QQ"
        )
        return m.available_for == ["QQ"]
    except Exception:
        return False


def _test_module_to_dict():
    """Module.to_dict: 应返回完整字典"""
    try:
        m = Module.assign(
            module_name="test_mod", alias=None, recommend_modules=None, developers=None, desc="Test module"
        )
        d = m.to_dict()
        return d["module_name"] == "test_mod" and d["desc"] == "Test module" and "commands" in d and "regexp" in d
    except Exception:
        return False


def _test_module_command_matches_init():
    """Module: command_list 应初始化为空"""
    try:
        m = Module.assign(module_name="test_mod", alias=None, recommend_modules=None, developers=None)
        return len(m.command_list.set) == 0
    except Exception:
        return False


def _test_module_regex_matches_init():
    """Module: regex_list 应初始化为空"""
    try:
        m = Module.assign(module_name="test_mod", alias=None, recommend_modules=None, developers=None)
        return len(m.regex_list.set) == 0
    except Exception:
        return False


@func_case
async def test_component(tester: Tester):
    """core.component: 组件注册系统测试"""
    await tester.test(_test_bind_module_create, "Bind.Module 创建测试")
    await tester.test(_test_module_assign_basic, "Module.assign 基本创建测试")
    await tester.test(_test_module_assign_alias_str, "Module.assign 字符串别名测试")
    await tester.test(_test_module_assign_alias_list, "Module.assign 列表别名测试")
    await tester.test(_test_module_assign_alias_dict, "Module.assign 字典别名测试")
    await tester.test(_test_module_assign_flags, "Module.assign 标志位测试")
    await tester.test(_test_module_assign_available_for, "Module.assign available_for 测试")
    await tester.test(_test_module_to_dict, "Module.to_dict 测试")
    await tester.test(_test_module_command_matches_init, "Module command_list 初始化测试")
    await tester.test(_test_module_regex_matches_init, "Module regex_list 初始化测试")
    return tester
