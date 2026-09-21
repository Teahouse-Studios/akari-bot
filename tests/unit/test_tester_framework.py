"""测试框架自身的单元测试。"""

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
    response = MockHTTPResponse(status_code=200, text="{}", content=b"binary")
    missing = [fmt for fmt in REQUIRED_RESPONSE_FORMATS if not hasattr(response, fmt)]
    if missing:
        Logger.error(f"MockHTTPResponse missing formats: {missing}")
    return not missing


def _test_mock_response_read_returns_bytes():
    if MockHTTPResponse(content=b"\x89PNG").read() != b"\x89PNG":
        return False
    return MockHTTPResponse(text="abc").read() == b"abc"


async def _test_contains_matches_non_text_element():
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
    from core.builtins.message.elements import PlainElement

    result = {"output": [PlainElement.assign("hello")]}
    return not await Contains("definitely_absent_token").match(result)


def _test_expectation_has_repr():
    return repr(Contains("x")) == str(Contains("x")) and Expectation.__repr__ is not object.__repr__


def _test_junit_coerces_error_details_to_text():
    case = JUnitTestCase("error")
    case.error = ("Test error", True)
    suite = JUnitTestSuite("tester")
    suite.add_testcase(case)
    report = JUnitReport()
    report.add_testsuite(suite)
    return '<error message="Test error">True</error>' in report.to_xml_string()


async def _test_integrate_preserves_unexpected_exception():
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


async def _test_protocol_exception_is_recorded_without_stopping_function_test():
    from core.constants import WaitCancelException
    from core.tester.process import run_function_entry

    async def cancelled_wait():
        raise WaitCancelException

    async def fine():
        return True

    async def mixed(tester):
        await tester.test(cancelled_wait, "等待取消")
        await tester.test(fine, "后续测试")
        return tester

    orphan_cancelled = asyncio.Event()
    orphan_started = asyncio.Event()
    orphan_task = {}

    async def orphan():
        try:
            orphan_started.set()
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            orphan_cancelled.set()
            raise

    async def unhandled_protocol_exception(_tester):
        orphan_task["task"] = asyncio.create_task(orphan(), name="test-protocol-exception-orphan")
        await orphan_started.wait()
        raise WaitCancelException

    try:
        with (
            patch("core.tester.process.close_db", new=AsyncMock()),
            patch("core.tester.process.init_db", new=AsyncMock(return_value=True)),
            patch("core.tester.process.load_modules", new=AsyncMock()),
        ):
            result = await run_function_entry(mixed, is_ci=True)
            unhandled_result = await run_function_entry(unhandled_protocol_exception, is_ci=True)

        results = result.get("results", [])
        task = orphan_task.get("task")
        return (
            not result.get("error")
            and len(results) == 2
            and results[0].get("match") is False
            and results[0].get("exception_type") == "WaitCancelException"
            and results[1].get("match") is True
            and unhandled_result.get("error")
            and unhandled_result.get("cleanup_pending") is False
            and task is not None
            and task.done()
            and task.cancelled()
            and orphan_cancelled.is_set()
        )
    finally:
        task = orphan_task.get("task")
        if task is not None and not task.done():
            task.cancel()
        if task is not None:
            await asyncio.gather(task, return_exceptions=True)


async def _test_function_entries_cancel_orphaned_tasks_before_reinitializing_database():
    from core.tester.process import _cancel_orphan_tasks

    cancelled = asyncio.Event()

    async def orphan():
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.set()
            raise

    baseline = set(asyncio.all_tasks())
    task = asyncio.create_task(orphan(), name="test-orphaned-function-entry-task")
    await asyncio.sleep(0)
    return await _cancel_orphan_tasks(baseline) and task.cancelled() and cancelled.is_set()


async def _test_case_entry_cancels_orphaned_tasks_before_next_database_context():
    from core.tester.process import run_case_entry

    cancelled = asyncio.Event()
    orphan_task = None

    async def orphan():
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.set()
            raise

    async def fake_run_test_case(*_args, **_kwargs):
        nonlocal orphan_task
        orphan_task = asyncio.create_task(orphan(), name="test-orphaned-case-entry-task")
        await asyncio.sleep(0)
        return {"input": "~case", "output": [], "action": [], "expected": None}

    entry = {
        "func": lambda _msg: None,
        "input": "~case",
        "expected": None,
        "note": None,
        "timeout": None,
        "file": None,
        "line": 0,
    }
    with (
        patch("core.tester.process.close_db", new=AsyncMock()),
        patch("core.tester.process.init_db", new=AsyncMock(return_value=True)),
        patch("core.tester.process.load_modules", new=AsyncMock()),
        patch("core.tester.process.run_test_case", new=fake_run_test_case),
    ):
        await run_case_entry(entry, is_ci=True)
    return orphan_task is not None and orphan_task.cancelled() and cancelled.is_set()


async def _test_progress_notifications_coalesce_to_latest_revision():
    tester = Tester("progress_queue")
    revision = tester._progress_revision
    tester._notify_progress()
    tester._notify_progress()
    observed = await asyncio.wait_for(tester._wait_for_progress(revision), timeout=0.1)
    return observed == revision + 2


async def _test_function_entry_bounds_cancellation_cleanup():
    from core.tester.process import run_function_entry

    cleanup_started = asyncio.Event()
    release_cleanup = asyncio.Event()

    async def stuck_after_cancel():
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cleanup_started.set()
            await release_cleanup.wait()

    async def stubborn(tester):
        await tester.test(stuck_after_cancel, "延迟取消的子测试")

    try:
        with (
            patch("core.tester.process.close_db", new=AsyncMock()),
            patch("core.tester.process.init_db", new=AsyncMock(return_value=True)),
            patch("core.tester.process.load_modules", new=AsyncMock()),
            patch("core.tester.process.FUNCTION_TEST_CANCEL_TIMEOUT", 0.01),
        ):
            result = await asyncio.wait_for(run_function_entry(stubborn, is_ci=True, timeout=0.01), timeout=0.1)
        return result.get("timeout") is True and result.get("cleanup_pending") is True and cleanup_started.is_set()
    finally:
        release_cleanup.set()
        await asyncio.sleep(0)


async def _test_cancelled_progress_waiter_does_not_reset_deadline():
    from core.tester.process import run_function_entry

    async def cancelled_waiter(_self, _after_revision):
        raise asyncio.CancelledError

    async def stuck(_tester):
        await asyncio.Event().wait()

    with (
        patch("core.tester.process.close_db", new=AsyncMock()),
        patch("core.tester.process.init_db", new=AsyncMock(return_value=True)),
        patch("core.tester.process.load_modules", new=AsyncMock()),
        patch.object(Tester, "_wait_for_progress", new=cancelled_waiter),
    ):
        result = await asyncio.wait_for(run_function_entry(stuck, is_ci=True, timeout=0.01), timeout=0.1)
    return result.get("timeout") is True and result.get("cleanup_pending") is False


async def _test_unit_subtest_exception_keeps_running_and_counts_once():
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
    from core.tester.process import run_function_entry

    async def noop(_tester):
        return None

    with (
        patch("core.tester.process.close_db", new=AsyncMock()),
        patch("core.tester.process.init_db", new=AsyncMock(return_value=False)),
    ):
        result = await run_function_entry(noop, is_ci=True)
    return bool(result.get("error")) and not result.get("skipped")


def _test_union_merge_logs_stay_out_of_repo_data():
    from core.constants.path import data_path, union_merge_logs_path
    from core.database.models import UNION_SCOPE_SENDER
    from core.utils.union_merge import write_merge_log

    repo_logs_dir = data_path / "union_merge_logs"
    before = set(repo_logs_dir.glob("*.json")) if repo_logs_dir.is_dir() else set()

    new_union = "UNIONTEST|merge-log-isolation"
    write_merge_log(new_union, UNION_SCOPE_SENDER, {"keep_ids": [], "drop_ids": []})

    leaked = (set(repo_logs_dir.glob("*.json")) if repo_logs_dir.is_dir() else set()) - before
    if leaked:
        Logger.error(f"Merge logs leaked into {repo_logs_dir}: {sorted(path.name for path in leaked)}")
        return False

    # 写入本身仍须发生，只是落在隔离目录中；若日志改为空操作，泄漏检查会假通过。
    if not list(union_merge_logs_path.glob(f"*_{new_union.replace('|', '-')}.json")):
        Logger.error(f"Expected a merge log under {union_merge_logs_path}, found none")
        return False
    return True


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
    await tester.test(
        _test_protocol_exception_is_recorded_without_stopping_function_test,
        "业务控制流异常不终止 func_case 测试",
    )
    await tester.test(
        _test_function_entries_cancel_orphaned_tasks_before_reinitializing_database,
        "func_case 之间回收遗留任务测试",
    )
    await tester.test(
        _test_case_entry_cancels_orphaned_tasks_before_next_database_context,
        "注册表用例之间回收遗留任务测试",
    )
    await tester.test(
        _test_progress_notifications_coalesce_to_latest_revision,
        "连续进度通知合并到最新版本测试",
    )
    await tester.test(_test_function_entry_bounds_cancellation_cleanup, "func_case 取消收尾有界测试")
    await tester.test(
        _test_cancelled_progress_waiter_does_not_reset_deadline,
        "进度等待器取消不刷新 watchdog 测试",
    )
    await tester.test(_test_unit_subtest_exception_keeps_running_and_counts_once, "unit 子测试异常续跑且计数一次测试")
    await tester.test(_test_function_entry_does_not_misclassify_test_timeout, "子测试超时不冒充 runner 超时测试")
    await tester.test(_test_function_entry_init_failure_is_error, "func_case 初始化错误不可跳过测试")
    await tester.test(_test_union_merge_logs_stay_out_of_repo_data, "合并日志不落进 data/ 测试")

    return tester
