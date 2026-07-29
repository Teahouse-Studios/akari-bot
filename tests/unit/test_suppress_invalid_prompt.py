"""core.types.module 单元测试 - 模块级命令语法错误提示开关。"""

from core.tester import func_case, Tester
from core.types.module import Module


def _build(**kwargs):
    """构造一个最小可用的模块实例。"""
    defaults = {
        "module_name": "dummy",
        "alias": None,
        "recommend_modules": None,
        "developers": None,
    }
    defaults.update(kwargs)
    return Module.assign(**defaults)


async def _test_default_is_false():
    """测试语法错误提示开关 - 默认不抑制提示"""
    try:
        return _build().suppress_invalid_prompt is False

    except Exception:
        return False


async def _test_can_be_enabled():
    """测试语法错误提示开关 - 可显式开启"""
    try:
        return _build(suppress_invalid_prompt=True).suppress_invalid_prompt is True

    except Exception:
        return False


async def _test_included_in_to_dict():
    """测试语法错误提示开关 - 纳入 to_dict 序列化"""
    try:
        return _build(suppress_invalid_prompt=True).to_dict()["suppress_invalid_prompt"] is True

    except Exception:
        return False


@func_case
async def test_suppress_invalid_prompt(tester: Tester):
    """core.types.module: 命令语法错误提示开关测试"""
    await tester.test(_test_default_is_false, "默认不抑制测试")
    await tester.test(_test_can_be_enabled, "显式开启测试")
    await tester.test(_test_included_in_to_dict, "序列化包含测试")

    return tester
