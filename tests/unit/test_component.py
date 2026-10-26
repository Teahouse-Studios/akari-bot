"""core.component 组件注册系统单元测试。"""

from core.tester import func_case, Tester
from core.types import Module


def _test_module_assign_basic():
    try:
        m = Module.assign(module_name="test_mod", alias=None, recommend_modules=None, developers=None)
        return m.module_name == "test_mod" and m.base is False and m.load is True
    except Exception:
        return False


def _test_module_assign_alias_str():
    try:
        m = Module.assign(module_name="test_mod", alias="tm", recommend_modules=None, developers=None)
        return m.alias == {"tm": "test_mod"}
    except Exception:
        return False


def _test_module_assign_alias_list():
    try:
        m = Module.assign(module_name="test_mod", alias=["t1", "t2"], recommend_modules=None, developers=None)
        return m.alias == {"t1": "test_mod", "t2": "test_mod"}
    except Exception:
        return False


def _test_module_assign_available_for():
    try:
        m = Module.assign(
            module_name="test_mod", alias=None, recommend_modules=None, developers=None, available_for="QQ"
        )
        return m.available_for == ["QQ"]
    except Exception:
        return False


def _test_module_to_dict():
    try:
        m = Module.assign(
            module_name="test_mod", alias=None, recommend_modules=None, developers=None, desc="Test module"
        )
        d = m.to_dict()
        return d["module_name"] == "test_mod" and d["desc"] == "Test module" and "commands" in d and "regexp" in d
    except Exception:
        return False


def _test_module_bot_permission_requirements():
    try:
        m = Module.assign(
            module_name="test_mod",
            alias=None,
            recommend_modules=None,
            developers=None,
            event=True,
            rss=True,
            required_bot_permissions="can_manage_members",
        )
        return (
            m.required_bot_permissions == ["can_manage_members"]
            and m.bot_permissions_for_enable()
            == ["can_manage_members", "can_read_all_messages", "can_send_proactive_messages"]
            and m.to_dict()["required_bot_permissions"] == ["can_manage_members"]
        )
    except Exception:
        return False


@func_case
async def test_component(tester: Tester):
    """core.component: 组件注册系统测试"""
    await tester.test(_test_module_assign_basic, "Module.assign 基本创建测试")
    await tester.test(_test_module_assign_alias_str, "Module.assign 字符串别名测试")
    await tester.test(_test_module_assign_alias_list, "Module.assign 列表别名测试")
    await tester.test(_test_module_assign_available_for, "Module.assign available_for 测试")
    await tester.test(_test_module_to_dict, "Module.to_dict 测试")
    await tester.test(_test_module_bot_permission_requirements, "Module 机器人权限需求测试")
    return tester
