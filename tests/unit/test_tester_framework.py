"""测试框架自身的单元测试。

框架的 mock 对象需要与被替身的真实实现保持接口一致。一旦真实实现新增参数而
mock 未同步，模块代码会在测试中抛出 TypeError，且失败信息与被测逻辑毫无关系，
排查成本极高。此处将这类一致性约束固化为断言。
"""

import inspect
import re
import asyncio
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock, patch

from core.builtins.session.internal import MessageSession
from core.tester import func_case, Tester, Raise
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


async def _test_integrate_preserves_unexpected_exception():
    """func_case 的普通断言失败时应保留命令异常与 traceback。"""
    error = ValueError("boom")
    raw_result = {
        "input": "~broken",
        "exception": error,
        "exception_message": "boom",
        "traceback": "traceback: boom",
        "action": ["(raise ValueError)", "boom"],
        "output": None,
    }
    tester = Tester("exception")
    with patch("core.tester.tester.run_test_case", new=AsyncMock(return_value=raw_result)):
        result = await tester.integrate("~broken", Contains("success"))
    return (
        result.get("match") is False
        and result.get("exception") is error
        and result.get("traceback") == "traceback: boom"
    )


async def _test_integrate_expected_exception_is_not_runner_error():
    """Raise 命中预期异常后应通过，并移除仅供失败报告使用的 traceback。"""
    error = ValueError("boom")
    raw_result = {
        "input": "~broken",
        "exception": error,
        "exception_message": "boom",
        "traceback": "traceback: boom",
        "action": ["(raise ValueError)", "boom"],
        "output": None,
    }
    tester = Tester("expected_exception")
    with patch("core.tester.tester.run_test_case", new=AsyncMock(return_value=raw_result)):
        result = await tester.integrate("~broken", Raise(ValueError, "boom"))
    return result.get("match") is True and "traceback" not in result


async def _test_function_entry_timeout_is_structured_failure():
    """无进展的 func_case 应超时返回，不能阻塞整个测试列表。"""
    from core.tester.process import run_function_entry

    async def stuck():
        await asyncio.Event().wait()

    async def slow(tester):
        await tester.test(stuck, "卡住的子测试")

    with (
        patch("core.tester.process.close_db", new=AsyncMock()),
        patch("core.tester.process.init_db", new=AsyncMock(return_value=True)),
        patch("core.tester.process.load_modules", new=AsyncMock()),
    ):
        result = await run_function_entry(slow, is_ci=True, timeout=0.01)
    return (
        result.get("timeout") is True
        and result.get("timeout_limit") == 0.01
        and result.get("active_test") == "卡住的子测试"
        and result.get("completed_tests") == 0
    )


async def _test_function_entry_timeout_resets_on_progress():
    """func_case 持续完成子测试时，总耗时超过单次超时仍应通过。"""
    from core.tester.process import run_function_entry

    async def step():
        await asyncio.sleep(0.02)
        return True

    async def progressing(tester):
        for _ in range(12):
            await tester.test(step)
        return tester

    with (
        patch("core.tester.process.close_db", new=AsyncMock()),
        patch("core.tester.process.init_db", new=AsyncMock(return_value=True)),
        patch("core.tester.process.load_modules", new=AsyncMock()),
    ):
        result = await run_function_entry(progressing, is_ci=True, timeout=0.2)
    return not result.get("timeout") and all(entry.get("match") for entry in result.get("results", []))


async def _test_unit_subtest_exception_keeps_running_and_counts_once():
    """unit 子测试抛异常应记录后继续跑后续子测试，runner 只计一次失败。"""
    import tester as tester_module

    async def boom():
        raise RuntimeError("unit boom")

    async def fine():
        return True

    from core.tester.decorator import func_case as _fc

    @_fc
    async def mixed(tester):
        await tester.test(boom, "失败子测试")
        await tester.test(fine, "成功子测试")
        return tester

    with (
        patch("core.tester.process.close_db", new=AsyncMock()),
        patch("core.tester.process.init_db", new=AsyncMock(return_value=True)),
        patch("core.tester.process.load_modules", new=AsyncMock()),
    ):
        from core.tester.process import run_function_entry

        res = await run_function_entry(mixed, is_ci=True)

    class FakeSuite:
        def __init__(self, name):
            self.name = name
            self.test_cases = []

        def add_testcase(self, tc):
            self.test_cases.append(tc)

    func_suite = FakeSuite("Function Tests")
    registry_suite = FakeSuite("Registry Tests")

    class _NullLogger:
        def __getattr__(self, name):
            return lambda *args, **kwargs: None

    fake_spec = types.SimpleNamespace(
        name="tests__fake_case",
        loader=types.SimpleNamespace(exec_module=lambda mod: None),
    )
    original_modules = dict(sys.modules)

    with (
        patch.object(tester_module, "Logger", _NullLogger()),
        patch.object(tester_module, "init_db", new=AsyncMock(return_value=True)),
        patch.object(tester_module, "close_db", new=AsyncMock()),
        patch.object(tester_module, "load_modules", new=AsyncMock()),
        patch.object(tester_module, "get_registry", return_value=[]),
        patch.object(tester_module, "run_function_entry", new=AsyncMock(return_value=res)),
        patch.object(tester_module.glob, "glob", return_value=[str(Path("tests/unit/_fake_case.py"))]),
        patch.object(tester_module.importlib.util, "spec_from_file_location", return_value=fake_spec),
        patch.object(tester_module, "junit_func_suite", func_suite),
        patch.object(tester_module, "junit_registry_suite", registry_suite),
        patch.object(tester_module, "junit_report") as junit_report,
        patch.object(tester_module.os.path, "isdir", return_value=True),
        patch.object(tester_module.importlib.util, "module_from_spec", return_value=types.SimpleNamespace()),
    ):
        sys.modules.clear()
        sys.modules.update(original_modules)
        junit_report.test_suites = []
        fake_inspect = types.SimpleNamespace(
            getmembers=lambda mod, predicate=None: [("mixed", mixed)],
            isfunction=lambda obj: obj is mixed,
        )
        await tester_module.main(inspect_module=fake_inspect)

    names = [tc.name for tc in func_suite.test_cases]
    failed_cases = [tc for tc in func_suite.test_cases if tc.failure or tc.error]
    checks = {
        "exception_recorded": res["results"][0].get("exception_type") == "RuntimeError",
        "kept_running": len(res["results"]) == 2 and res["results"][1].get("match") is True,
        "two_cases": len(func_suite.test_cases) == 2,
        "no_double_count": len(failed_cases) == 2,
        "subtest_named": any("失败子测试" in name for name in names),
    }
    if not all(checks.values()):
        raise AssertionError(
            f"runner accounting regression: {checks}; "
            f"cases={[(tc.name, bool(tc.failure), bool(tc.error)) for tc in func_suite.test_cases]}"
        )
    return True


async def _test_function_entry_does_not_misclassify_test_timeout():
    """子测试自身的 TimeoutError 应保留堆栈，不能冒充 runner 无进展超时。"""
    from core.tester.process import run_function_entry

    async def inner_timeout():
        raise TimeoutError("inner deadline")

    async def timed_test(tester):
        await tester.test(inner_timeout, "内部超时")
        return tester

    with (
        patch("core.tester.process.close_db", new=AsyncMock()),
        patch("core.tester.process.init_db", new=AsyncMock(return_value=True)),
        patch("core.tester.process.load_modules", new=AsyncMock()),
    ):
        result = await run_function_entry(timed_test, is_ci=True, timeout=0.2)
    (subtest,) = result.get("results", [])
    return (
        not result.get("timeout")
        and subtest.get("match") is False
        and subtest.get("exception_type") == "TimeoutError"
        and "inner deadline" in subtest.get("exception_message", "")
        and "inner deadline" in subtest.get("traceback", "")
        and subtest.get("note") == "内部超时"
    )


async def _test_function_entry_init_failure_is_error():
    """数据库初始化失败属于基础设施错误，不能被记为跳过或通过。"""
    from core.tester.process import run_function_entry

    async def noop(_tester):
        return None

    with (
        patch("core.tester.process.close_db", new=AsyncMock()),
        patch("core.tester.process.init_db", new=AsyncMock(return_value=False)),
    ):
        result = await run_function_entry(noop, is_ci=True)
    return bool(result.get("error")) and not result.get("skipped")


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
    await tester.test(_test_integrate_preserves_unexpected_exception, "func_case 保留非预期异常测试")
    await tester.test(_test_integrate_expected_exception_is_not_runner_error, "func_case 预期异常匹配测试")
    await tester.test(_test_function_entry_timeout_is_structured_failure, "func_case 超时结构化失败测试")
    await tester.test(_test_function_entry_timeout_resets_on_progress, "func_case 超时按进展刷新测试")
    await tester.test(_test_unit_subtest_exception_keeps_running_and_counts_once, "unit 子测试异常续跑且计数一次测试")
    await tester.test(_test_function_entry_does_not_misclassify_test_timeout, "子测试超时不冒充 runner 超时测试")
    await tester.test(_test_function_entry_init_failure_is_error, "func_case 初始化错误不可跳过测试")

    return tester
