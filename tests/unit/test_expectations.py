"""Expectation 匹配器自身正确性测试。"""

from core.tester import (
    func_case,
    Tester,
    Contains,
    Match,
    StartsWith,
    EndsWith,
    Regex,
    Empty,
    Length,
    Predicate,
    All,
    Any,
    Not,
    AnyOutput,
    NoException,
)


def _test_predicate(result):
    """测试 Predicate 匹配器"""
    output = result.get("output")
    return bool(output)


@func_case
async def test_expectations(tester: Tester):
    """Expectation 匹配器: 各类型匹配器测试"""
    # AnyOutput 匹配器
    await tester.expect("~ping", AnyOutput(), "AnyOutput 有输出")

    # Contains 匹配器
    await tester.expect("~ping", Contains("Pong"), "Contains 包含文本")

    # Empty 匹配器
    await tester.expect("~nonexistent_command_xyz_12345", Empty(), "Empty 无输出")

    # NoException 匹配器
    await tester.expect("~ping", NoException(), "NoException 正常执行")

    # Predicate 匹配器
    await tester.expect("~ping", Predicate(_test_predicate), "Predicate 自定义匹配")

    # 组合匹配器 - All (AND)
    await tester.expect("~ping", All(Contains("Pong"), AnyOutput()), "All 组合匹配")

    # 组合匹配器 - Any (OR)
    await tester.expect("~ping", Any(Contains("Pong"), Contains("nonexistent_text")), "Any 组合匹配")

    # 组合匹配器 - Not
    await tester.expect("~ping", Not(Contains("nonexistent_text_xyz")), "Not 组合匹配")

    # 运算符组合 - &
    await tester.expect("~ping", Contains("Pong") & AnyOutput(), "& 运算符组合")

    # 运算符组合 - |
    await tester.expect("~ping", Contains("Pong") | Contains("nonexistent"), "| 运算符组合")

    # 运算符组合 - ~
    await tester.expect("~ping", ~Contains("nonexistent_text_xyz"), "~ 运算符组合")

    return tester


@func_case
async def test_match_matcher(tester: Tester):
    """Match 匹配器: 精确匹配测试"""
    # Match 做全量精确比较，~ping 输出多行，用否定测试验证 Match 能力
    await tester.expect("~ping", ~Match("nonexistent_text_xyz_12345"), "Match 不匹配时应返回 False")
    return tester


@func_case
async def test_startswith_matcher(tester: Tester):
    """StartsWith 匹配器: 前缀匹配测试"""
    await tester.expect("~ping", StartsWith("Pong"), "StartsWith 前缀匹配")
    return tester


@func_case
async def test_endswith_matcher(tester: Tester):
    """EndsWith 匹配器: 后缀匹配测试"""
    await tester.expect("~version", EndsWith("。"), "EndsWith 后缀匹配")
    return tester


@func_case
async def test_regex_matcher(tester: Tester):
    """Regex 匹配器: 正则匹配测试"""
    await tester.expect("~ping", Regex(r"Pong"), "Regex 正则匹配")
    return tester


@func_case
async def test_length_matcher(tester: Tester):
    """Length 匹配器: 消息链长度测试"""
    await tester.expect("~ping", Length(ge=1), "Length 至少1个元素")
    return tester


@func_case
async def test_contains_case_sensitive(tester: Tester):
    """Contains 匹配器: 大小写敏感测试"""
    await tester.expect("~ping", Contains("pong", case_sensitive=False), "Contains 不区分大小写")
    return tester


@func_case
async def test_noexception_matcher(tester: Tester):
    """NoException 匹配器: 正常执行测试"""
    await tester.expect("~ping", NoException(), "NoException 正常执行")
    return tester
