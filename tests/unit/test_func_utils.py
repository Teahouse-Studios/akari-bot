"""core.utils.func 纯函数单元测试。"""

from datetime import timedelta

from core.tester import func_case, Tester
from core.utils.func import (
    convert_list,
    is_iterable,
    is_json_serializable,
    chunk_list,
    unique_list,
    flatten_list,
    flatten_dict,
    unflatten_dict,
    is_float,
    is_int,
    camel_to_snake,
    snake_to_camel,
    normalize_space,
    truncate_text,
    parse_time_string,
    generate_progress_bar,
)


def _test_convert_list():
    """测试 convert_list 函数"""
    return (
        convert_list(None) == []
        and convert_list([1, 2]) == [1, 2]
        and convert_list((1, 2)) == [1, 2]
        and set(convert_list({1, 2})) == {1, 2}
        and convert_list("hello") == ["hello"]
        and convert_list(42) == [42]
    )


def _test_is_iterable():
    """测试 is_iterable 函数"""
    return (
        is_iterable([1, 2]) is True
        and is_iterable((1, 2)) is True
        and is_iterable({1, 2}) is True
        and is_iterable(range(5)) is True
        and is_iterable("hello") is False
        and is_iterable(b"hello") is False
        and is_iterable(42) is False
        and is_iterable(None) is False
    )


def _test_is_json_serializable():
    """测试 is_json_serializable 函数"""
    return (
        is_json_serializable({"a": 1}) is True
        and is_json_serializable([1, 2, 3]) is True
        and is_json_serializable("hello") is True
        and is_json_serializable(42) is True
        and is_json_serializable(3.14) is True
        and is_json_serializable(True) is True
        and is_json_serializable(None) is True
        and is_json_serializable(object()) is False
        and is_json_serializable(lambda x: x) is False
    )


def _test_chunk_list():
    """测试 chunk_list 函数"""
    try:
        return (
            list(chunk_list([1, 2, 3, 4, 5], 2)) == [[1, 2], [3, 4], [5]]
            and list(chunk_list([1, 2, 3, 4], 2)) == [[1, 2], [3, 4]]
            and list(chunk_list([1, 2], 5)) == [[1, 2]]
            and list(chunk_list([], 2)) == []
            and list(chunk_list([1, 2, 3, 4, 5], 2, reverse=True)) == [[5, 4], [3, 2], [1]]
        )
    except Exception:
        return False


def _test_unique_list():
    """测试 unique_list 函数"""
    try:
        if unique_list([1, 2, 2, 3, 3, 3]) != [1, 2, 3]:
            return False
        if unique_list([3, 1, 2, 1, 3]) != [3, 1, 2]:
            return False
        if unique_list([]) != []:
            return False
        if unique_list([1]) != [1]:
            return False
        return True
    except Exception:
        return False


def _test_flatten_list():
    """测试 flatten_list 函数"""
    try:
        return (
            flatten_list([1, [2, 3], [4, [5, 6]]]) == [1, 2, 3, 4, 5, 6]
            and flatten_list([1, 2, 3]) == [1, 2, 3]
            and flatten_list([]) == []
            and flatten_list([[1], [[2]], [[[3]]]]) == [1, 2, 3]
            and flatten_list([1, "hello", [2, "world"]]) == [1, "hello", 2, "world"]
        )
    except Exception:
        return False


def _test_flatten_dict():
    """测试 flatten_dict / unflatten_dict 函数"""
    try:
        d = {"a": 1, "b": {"c": 2, "d": {"e": 3}}}
        flat = flatten_dict(d)
        flat2 = flatten_dict(d, sep="/")
        unflat = unflatten_dict(flat)
        return (
            flat == {"a": 1, "b.c": 2, "b.d.e": 3}
            and flat2 == {"a": 1, "b/c": 2, "b/d/e": 3}
            and unflat == d
            and flatten_dict({}) == {}
            and unflatten_dict({}) == {}
        )
    except Exception:
        return False


def _test_is_float_is_int():
    """测试 is_float / is_int 函数"""
    return (
        is_float("3.14") is True
        and is_float("42") is True
        and is_float("-1.5") is True
        and is_float("abc") is False
        and is_int("42") is True
        and is_int("0") is True
        and is_int("-5") is True
        and is_int(42.0) is True
        and is_int(42.5) is False
        and is_int("abc") is False
    )


def _test_case_conversion():
    """测试 camel_to_snake / snake_to_camel 函数"""
    return (
        camel_to_snake("CamelCase") == "camel_case"
        and camel_to_snake("simpleTest") == "simple_test"
        and snake_to_camel("camel_case") == "CamelCase"
        and snake_to_camel("simple_test") == "SimpleTest"
        and snake_to_camel("camel_case", upper=False) == "camelCase"
    )


def _test_normalize_space():
    """测试 normalize_space 函数"""
    return (
        normalize_space("  hello   world  ") == "hello world"
        and normalize_space("hello") == "hello"
        and normalize_space("  ") == ""
        and normalize_space("") == ""
        and normalize_space("a  b  c  d") == "a b c d"
    )


def _test_truncate_text():
    """测试 truncate_text 函数"""
    return (
        truncate_text("hello", 10) == "hello"
        and truncate_text("hello world", 5) == "hello..."
        and truncate_text("hello world", 5, suffix="…") == "hello…"
        and truncate_text("", 5) == ""
    )


def _test_parse_time_string():
    """测试 parse_time_string 函数"""
    return (
        parse_time_string("+8:00") == timedelta(hours=8)
        and parse_time_string("-5:30") == timedelta(hours=-5, minutes=-30)
        and parse_time_string("+0:00") == timedelta()
        and parse_time_string("8:00") == timedelta(hours=8)
        and parse_time_string("+9") == timedelta(hours=9)
        and parse_time_string("invalid") == timedelta()
    )


def _test_generate_progress_bar():
    """测试 generate_progress_bar 函数"""
    bar1 = generate_progress_bar(75, 100)
    bar2 = generate_progress_bar(100, 100)
    bar3 = generate_progress_bar(0, 100)
    bar4 = generate_progress_bar(0, 0)
    bar5 = generate_progress_bar(50, 100, show_number=True)
    bar6 = generate_progress_bar(50, 100, show_percent=False)
    return (
        "75.0%" in bar1
        and "100.0%" in bar2
        and "0.0%" in bar3
        and "0.0%" in bar4
        and "50/100" in bar5
        and "%" not in bar6
    )


@func_case
async def test_func_utils(tester: Tester):
    """core.utils.func: 所有工具函数测试"""
    await tester.test(_test_convert_list, "convert_list 测试")
    await tester.test(_test_is_iterable, "is_iterable 测试")
    await tester.test(_test_is_json_serializable, "is_json_serializable 测试")
    await tester.test(_test_chunk_list, "chunk_list 测试")
    await tester.test(_test_unique_list, "unique_list 测试")
    await tester.test(_test_flatten_list, "flatten_list 测试")
    await tester.test(_test_flatten_dict, "flatten_dict 测试")
    await tester.test(_test_is_float_is_int, "is_float/is_int 测试")
    await tester.test(_test_case_conversion, "camel_to_snake/snake_to_camel 测试")
    await tester.test(_test_normalize_space, "normalize_space 测试")
    await tester.test(_test_truncate_text, "truncate_text 测试")
    await tester.test(_test_parse_time_string, "parse_time_string 测试")
    await tester.test(_test_generate_progress_bar, "generate_progress_bar 测试")
    return tester
