"""core.builtins.parser.message 单元测试 - 正则单次触发标记。"""

from core.builtins.parser.message import mark_regex_once, regex_once_cache, regex_once_triggered
from core.tester import func_case, Tester


async def _test_not_triggered_before_mark():
    """测试单次触发 - 标记前判定为未触发"""
    try:
        regex_once_cache.clear()
        return not regex_once_triggered("merge", 0, "QQ|Group|1")

    except Exception:
        return False


async def _test_triggered_after_mark():
    """测试单次触发 - 标记后判定为已触发"""
    try:
        regex_once_cache.clear()
        mark_regex_once("merge", 0, "QQ|Group|1")
        return regex_once_triggered("merge", 0, "QQ|Group|1")

    except Exception:
        return False


async def _test_other_target_unaffected():
    """测试单次触发 - 标记不影响其他场景"""
    try:
        regex_once_cache.clear()
        mark_regex_once("merge", 0, "QQ|Group|1")
        return not regex_once_triggered("merge", 0, "QQ|Group|2")

    except Exception:
        return False


async def _test_other_index_unaffected():
    """测试单次触发 - 同模块的另一条正则互不影响"""
    try:
        regex_once_cache.clear()
        mark_regex_once("merge", 0, "QQ|Group|1")
        return not regex_once_triggered("merge", 1, "QQ|Group|1")

    except Exception:
        return False


@func_case
async def test_regex_trigger_once(tester: Tester):
    """core.builtins.parser.message: 正则单次触发标记测试"""
    await tester.test(_test_not_triggered_before_mark, "标记前未触发测试")
    await tester.test(_test_triggered_after_mark, "标记后已触发测试")
    await tester.test(_test_other_target_unaffected, "场景间互不影响测试")
    await tester.test(_test_other_index_unaffected, "同模块多正则互不影响测试")

    return tester
