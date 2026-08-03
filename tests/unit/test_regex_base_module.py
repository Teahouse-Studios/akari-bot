"""core.builtins.parser.message 单元测试 - base 模块的 regex 启用判定。"""

from types import SimpleNamespace

from core.builtins.parser.message import regex_module_enabled
from core.tester import func_case, Tester


def _fake_module(base: bool, regex: bool = False):
    """构造模块替身，regex_module_enabled 只读取 base 与 regex 两个字段。

    :param base: 是否为 base 模块。
    :param regex: 是否为正则模块。
    """
    return SimpleNamespace(base=base, regex=regex)


async def _test_base_module_enabled_without_enabling():
    """测试 regex 启用判定 - base 模块无须在场景中启用"""
    try:
        return regex_module_enabled(_fake_module(True), "merge", [])

    except Exception:
        return False


async def _test_normal_module_requires_enabling():
    """测试 regex 启用判定 - 非 base 模块仍须在场景中启用"""
    try:
        disabled = regex_module_enabled(_fake_module(False), "wiki", [])
        enabled = regex_module_enabled(_fake_module(False), "wiki", ["wiki"])
        return not disabled and enabled

    except Exception:
        return False


async def _test_none_enabled_modules_is_safe():
    """测试 regex 启用判定 - enabled_modules 为 None 时不抛异常"""
    try:
        return regex_module_enabled(_fake_module(True), "merge", None) and not regex_module_enabled(
            _fake_module(False), "wiki", None
        )

    except Exception:
        return False


@func_case
async def test_regex_base_module(tester: Tester):
    """core.builtins.parser.message: base 模块 regex 启用判定测试"""
    await tester.test(_test_base_module_enabled_without_enabling, "base 模块免启用测试")
    await tester.test(_test_normal_module_requires_enabling, "普通模块需启用测试")
    await tester.test(_test_none_enabled_modules_is_safe, "enabled_modules 为 None 测试")

    return tester
