"""测试框架自身的单元测试。

框架的 mock 对象需要与被替身的真实实现保持接口一致。一旦真实实现新增参数而
mock 未同步，模块代码会在测试中抛出 TypeError，且失败信息与被测逻辑毫无关系，
排查成本极高。此处将这类一致性约束固化为断言。
"""

import inspect
import re

from core.builtins.session.internal import MessageSession
from core.tester import func_case, Tester
from core.tester.expectations import Contains, ContainsAll, ContainsAny, Expectation, Regex
from core.tester.junit import JUnitReport, JUnitTestCase, JUnitTestSuite
from core.tester.mock.http import MockHTTPResponse
from core.tester.mock.session import MockMessageSession
from core.logger import Logger

# request_url 支持以 fmt 指定返回形式，mock 响应必须覆盖代码库中实际用到的全部取值。
REQUIRED_RESPONSE_FORMATS = ("json", "text", "read", "content")


def _test_mock_session_signature_matches_real():
    """MockMessageSession 覆写的方法不得遗漏真实 MessageSession 的参数"""
    drifted = {}
    for name in dir(MessageSession):
        if name.startswith("__"):
            continue
        real = getattr(MessageSession, name, None)
        mock = MockMessageSession.__dict__.get(name)
        if mock is None or not callable(real) or not callable(mock):
            continue
        try:
            real_params = inspect.signature(real).parameters
            mock_params = inspect.signature(mock).parameters
        except (ValueError, TypeError):
            continue
        missing = [p for p in real_params if p not in mock_params]
        if missing:
            drifted[name] = missing

    if drifted:
        Logger.error(f"MockMessageSession signature drift: {drifted}")
    return not drifted


def _test_mock_response_supports_all_formats():
    """MockHTTPResponse 需支持 request_url 全部 fmt 取值，否则 fixture 无法覆盖对应请求"""
    response = MockHTTPResponse(status_code=200, text="{}", content=b"binary")
    missing = [fmt for fmt in REQUIRED_RESPONSE_FORMATS if not hasattr(response, fmt)]
    if missing:
        Logger.error(f"MockHTTPResponse missing formats: {missing}")
    return not missing


def _test_mock_response_read_returns_bytes():
    """read() 应返回二进制内容，未录制二进制时回退为 text 编码"""
    if MockHTTPResponse(content=b"\x89PNG").read() != b"\x89PNG":
        return False
    return MockHTTPResponse(text="abc").read() == b"abc"


async def _test_contains_matches_non_text_element():
    """文本搜索类断言应能命中图片等非文本元素的渲染结果"""
    from core.builtins.message.elements import ImageElement, PlainElement

    result = {"output": [PlainElement.assign("hello"), ImageElement.assign(path="https://example.com/a.png")]}
    return (
        await Contains("KE:image").match(result)
        and await Contains("hello").match(result)
        and await Regex(re.compile(r"\[KE:image")).match(result)
        and await ContainsAll("hello", "KE:image").match(result)
        and await ContainsAny("nope", "KE:image").match(result)
    )


async def _test_contains_still_rejects_absent_text():
    """回退匹配不得放宽到误报：输出中不存在的文本仍应判定为不匹配"""
    from core.builtins.message.elements import PlainElement

    result = {"output": [PlainElement.assign("hello")]}
    return not await Contains("definitely_absent_token").match(result)


def _test_expectation_has_repr():
    """断言器需提供 __repr__，否则失败日志只能显示内存地址"""
    return repr(Contains("x")) == str(Contains("x")) and Expectation.__repr__ is not object.__repr__


def _test_junit_coerces_error_details_to_text():
    """JUnit 报告不得因异常详情不是字符串而整体生成失败"""
    case = JUnitTestCase("error")
    case.error = ("Test error", True)
    suite = JUnitTestSuite("tester")
    suite.add_testcase(case)
    report = JUnitReport()
    report.add_testsuite(suite)
    return '<error message="Test error">True</error>' in report.to_xml_string()


@func_case
async def test_tester_framework(tester: Tester):
    """core.tester: 测试框架自身一致性测试"""
    await tester.test(_test_mock_session_signature_matches_real, "mock 会话签名与真实实现一致测试")
    await tester.test(_test_mock_response_supports_all_formats, "mock 响应支持全部 fmt 测试")
    await tester.test(_test_mock_response_read_returns_bytes, "mock 响应 read() 返回二进制测试")
    await tester.test(_test_contains_matches_non_text_element, "文本断言命中非文本元素测试")
    await tester.test(_test_contains_still_rejects_absent_text, "文本断言不误报测试")
    await tester.test(_test_expectation_has_repr, "断言器可读表示测试")
    await tester.test(_test_junit_coerces_error_details_to_text, "JUnit 异常详情文本化测试")

    return tester
