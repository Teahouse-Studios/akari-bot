"""直接验证匹配器的正反例；命令执行由 integration 用例覆盖。"""

from core.builtins.message.elements import PlainElement
from core.tester import (
    All,
    Any,
    AnyOutput,
    Contains,
    Empty,
    Length,
    Match,
    NoException,
    Not,
    Predicate,
    Regex,
    StartsWith,
    EndsWith,
    Tester,
    func_case,
)


def _output(text):
    return {"output": [PlainElement.assign(text)] if text is not None else []}


async def _test_text_matchers():
    cases = (
        (Match("Pong!"), "Pong!", "Pong"),
        (Contains("pong"), "Pong!", "Ping!"),
        (Contains("pong", case_sensitive=True), "pong!", "Pong!"),
        (StartsWith("Pong"), "Pong!", "Say Pong!"),
        (EndsWith("Pong!"), "Say Pong!", "Pong! now"),
        (Regex(r"^Pong[0-9]+!$"), "Pong42!", "Pong!"),
    )
    for matcher, accepted, rejected in cases:
        assert await matcher.match(_output(accepted)), repr(matcher)
        assert not await matcher.match(_output(rejected)), repr(matcher)
    return True


async def _test_output_matchers():
    present, empty = _output("Pong!"), _output(None)
    assert await AnyOutput().match(present)
    assert not await AnyOutput().match(empty)
    assert not await AnyOutput().match(_output("执行命令时发生错误"))
    assert await Empty().match(empty) and not await Empty().match(present)
    for matcher in (Length(eq=1), Length(ge=1)):
        assert await matcher.match(present) and not await matcher.match(empty), repr(matcher)
    assert await NoException().match(present)
    assert not await NoException().match({"exception": ValueError("boom")})
    return True


async def _test_predicate_matcher():
    def has_output(result):
        return bool(result.get("output"))

    async def async_has_output(result):
        return has_output(result)

    for predicate in (has_output, async_has_output):
        matcher = Predicate(predicate)
        assert await matcher.match(_output("Pong!"))
        assert not await matcher.match(_output(None))
    return True


async def _test_combinators():
    result = _output("Pong!")
    matches = {True: Match("Pong!"), False: Match("Ping!")}
    # 两种拼写均覆盖真值表，防止恒真、恒假或只检查第一个条件。
    for left, right, conjunction, disjunction in (
        (True, True, True, True),
        (True, False, False, True),
        (False, True, False, True),
        (False, False, False, False),
    ):
        a, b = matches[left], matches[right]
        for matcher in (All(a, b), a & b):
            assert await matcher.match(result) is conjunction, repr(matcher)
        for matcher in (Any(a, b), a | b):
            assert await matcher.match(result) is disjunction, repr(matcher)
    for value, matcher in matches.items():
        assert await Not(matcher).match(result) is not value
        assert await (~matcher).match(result) is not value
    return True


@func_case
async def test_expectations(tester: Tester):
    """Expectation：文本、空输出、异常、自定义断言与组合条件。"""
    await tester.test(_test_text_matchers, "文本匹配器正反例与大小写敏感测试")
    await tester.test(_test_output_matchers, "输出数量、空输出和异常匹配测试")
    await tester.test(_test_predicate_matcher, "同步与异步 Predicate 正反例测试")
    await tester.test(_test_combinators, "组合匹配器与运算符真值表测试")
    return tester
