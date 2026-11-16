from core.version import check_python_version  # skipcq

check_python_version()  # noqa

import atexit
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

import tomlkit

# 引导代码不能放进 core 包：core.tester 等包的 __init__ 会导入配置模板，
# 而模板在导入期就读取配置项，此时临时配置尚未铺设。
TEST_CONFIG_PATH_ENV = "AKARI_CONFIG_PATH"  # 须与 core.constants.path.CONFIG_PATH_ENV 一致
TEST_CONFIG_TEMPLATE_PATH = Path("assets/config_store/zh_cn")

# union 合并日志目录，须与 core.constants.path.UNION_MERGE_LOGS_PATH_ENV 一致。
# 用例会真实走到合并流程，逐次写下的快照日志只在人工回溯真实合并时才有意义，
# 留在 data/ 里只会随每次测试运行越积越多。
TEST_UNION_MERGE_LOGS_PATH_ENV = "AKARI_UNION_MERGE_LOGS_PATH"

# 语言快照缓存目录。用例会导入 bot，而守护进程在导入期把该变量 setdefault 到
# data/i18n_cache；测试进程须先固定为自有的临时目录，否则框架启动时发布的快照
# 与之后的读取方（包括 spawn 出的子进程）会落在不同位置。
TEST_I18N_CACHE_DIR_ENV = "AKARI_BOT_I18N_CACHE_DIR"

TEST_CONFIG_OVERRIDES: list[tuple[str, str, str, object]] = [
    ("config.toml", "config", "enable_petal", True),
    # 通用测试进程不启动守护进程所管理的 WebSocket Hub。数据库后端
    # 作为自包含测试基座；WebSocket 的真实连接行为由专项用例显式建立 Hub 验证。
    ("jobqueue.toml", "jobqueue", "jobqueue_backend", "database"),
]


@dataclass(frozen=True)
class TestEnvironment:
    """本次测试运行实际使用的落盘路径。"""

    config_path: Path
    union_merge_logs_path: Path
    i18n_cache_path: Path


_environment: TestEnvironment | None = None
_created_paths: list[Path] = []


def _install_test_config() -> Path:
    path = Path(tempfile.mkdtemp(prefix="akari_test_config_"))
    if TEST_CONFIG_TEMPLATE_PATH.is_dir():
        shutil.copytree(TEST_CONFIG_TEMPLATE_PATH, path, dirs_exist_ok=True)

    for filename, table, key, value in TEST_CONFIG_OVERRIDES:
        file_path = path / filename
        document = tomlkit.parse(file_path.read_text(encoding="utf-8")) if file_path.is_file() else tomlkit.document()
        if table not in document:
            document[table] = tomlkit.table()
        document[table][key] = value
        file_path.write_text(tomlkit.dumps(document), encoding="utf-8")

    os.environ[TEST_CONFIG_PATH_ENV] = str(path)
    _created_paths.append(path)
    return path


def _install_test_union_merge_logs() -> Path:
    configured = os.environ.get(TEST_UNION_MERGE_LOGS_PATH_ENV)
    if configured:
        return Path(configured)

    path = Path(tempfile.mkdtemp(prefix="akari_test_union_merge_logs_"))
    os.environ[TEST_UNION_MERGE_LOGS_PATH_ENV] = str(path)
    _created_paths.append(path)
    return path


def _install_test_i18n_cache() -> Path:
    configured = os.environ.get(TEST_I18N_CACHE_DIR_ENV)
    if configured:
        return Path(configured)

    path = Path(tempfile.mkdtemp(prefix="akari_test_i18n_cache_"))
    os.environ[TEST_I18N_CACHE_DIR_ENV] = str(path)
    _created_paths.append(path)
    return path


def prepare_test_environment() -> TestEnvironment:
    """铺设测试环境并加载配置，重复调用返回同一份路径。"""
    global _environment
    if _environment is not None:
        return _environment

    config_path = _install_test_config()
    union_merge_logs_path = _install_test_union_merge_logs()
    i18n_cache_path = _install_test_i18n_cache()
    atexit.register(cleanup_test_environment)

    from core.builtins.config.bootstrap import bootstrap_config

    bootstrap_config()
    _environment = TestEnvironment(
        config_path=config_path,
        union_merge_logs_path=union_merge_logs_path,
        i18n_cache_path=i18n_cache_path,
    )
    return _environment


def cleanup_test_environment() -> None:
    """删除本次运行创建的临时目录；由环境变量显式指定的目录保留。"""
    while _created_paths:
        shutil.rmtree(_created_paths.pop(), ignore_errors=True)


test_environment = prepare_test_environment()

import asyncio
import glob
import importlib.util
import inspect
import sys
import traceback
from types import FunctionType
from typing import TypedDict

from dotenv import load_dotenv

from core.builtins.utils import confirm_command
from core.constants import ascii_art, cache_path, tests_path
from core.tester.decorator import CaseEntry, get_registry
from core.tester.expectations import Expectation
from core.tester.junit import JUnitReport, JUnitTestSuite, JUnitTestCase
from core.tester.logger import TestLoggingLogger
from core.tester.mock.database import close_db, get_last_init_error, init_db
from core.tester.mock.loader import load_modules
from core.tester.mock.random import Random
from core.tester.process import run_case_entry, run_function_entry

Logger = TestLoggingLogger("TEST")


load_dotenv()
os.environ.setdefault("PYTHONIOENCODING", "UTF-8")
os.environ.setdefault("PYTHONPATH", str(Path(".").resolve()))

IS_CI = os.environ.get("CI", "0") == "1"
ENABLE_COVERAGE = os.environ.get("COVERAGE", "0") == "1"
# 本机只跑部分整合测试时，用路径子串筛选
TEST_FILTER_ENV = "AKARI_TEST_FILTER"
INTEGRATION_TESTS_PATH = tests_path / "integration"

_coverage_instance = None
if ENABLE_COVERAGE:
    try:
        import coverage

        _coverage_instance = coverage.Coverage(
            source=["core", "modules"],
            omit=[
                "*/tests/*",
                "*/test_*",
                "*/__pycache__/*",
                "*/.venv/*",
            ],
        )
        _coverage_instance.start()
        Logger.info("Coverage collection enabled.")
    except ImportError:
        Logger.warning("coverage package not installed. Run: pip install coverage")
        _coverage_instance = None
    except Exception as e:
        Logger.warning(f"Failed to initialize coverage: {e}")
        _coverage_instance = None

junit_report = JUnitReport()
junit_registry_suite = JUnitTestSuite("Registry Tests")
junit_func_suite = JUnitTestSuite("Function Tests")


@dataclass
class RegistryTestStats:
    total: int = 0
    passed: int = 0
    failed: int = 0
    time_cost: float = 0.0


async def _run_registry_entry(entry: CaseEntry, test_number: int) -> dict:
    Logger.trace(f"_run_registry_entry START: TEST{test_number}")
    fn = entry["func"]
    note = entry.get("note") or (fn.__doc__ if fn.__doc__ else None)
    results = await run_case_entry(entry, IS_CI)
    Logger.trace(f"_run_registry_entry DONE: TEST{test_number}")
    return {"test_number": test_number, "results": results, "note": note}


async def _report_registry_case(
    entry: CaseEntry, reg_result: dict | Exception, test_number: int, stats: RegistryTestStats
) -> None:
    fn = entry["func"]
    file_loc = f"{entry.get('file')}:{entry.get('line')}"

    Logger.info(f"TEST{test_number}: {fn.__name__} ({file_loc})")
    if fn.__doc__:
        Logger.info(f"DOC: {fn.__doc__}")
    Logger.info("-" * 60)

    if isinstance(reg_result, Exception):
        Logger.error(f"Error during test execution: {reg_result}")
        stats.failed += 1
        stats.total += 1
        junit_testcase = JUnitTestCase(name=f"TEST{test_number}_runner", classname=f"RegistryTest.{test_number}")
        junit_testcase.error = ("Test runner error", repr(reg_result))
        junit_registry_suite.add_testcase(junit_testcase)
        return
    if not isinstance(reg_result, dict):
        stats.failed += 1
        stats.total += 1
        junit_testcase = JUnitTestCase(
            name=f"TEST{test_number}_invalid_result", classname=f"RegistryTest.{test_number}"
        )
        junit_testcase.error = ("Invalid test result", repr(reg_result))
        junit_registry_suite.add_testcase(junit_testcase)
        return

    note = reg_result.get("note")
    results = reg_result.get("results", [])
    for r in results:
        stats.total += 1
        inp = r.get("input")
        tcost = r.get("time_cost", 0.0)
        test_case_name = f"TEST{test_number}_{stats.total}"
        junit_testcase = JUnitTestCase(
            name=test_case_name, classname=f"RegistryTest.{test_number}", time=tcost if tcost else 0.0
        )

        if "timeout" in r:
            Logger.error(f"INPUT: {inp}")
            if note:
                Logger.error(f"NOTE: {note}")
            Logger.error("RESULT: FAIL (timeout)")
            stats.failed += 1
            junit_testcase.failure = (
                "Test timeout",
                f"Test exceeded timeout limit\nInput: {inp}\nNote: {note or 'N/A'}",
            )
            junit_registry_suite.add_testcase(junit_testcase)
            continue

        if "traceback" in r:
            Logger.error(f"INPUT: {inp}")
            if note:
                Logger.error(f"NOTE: {note}")
            Logger.error("ERROR during execution:")
            Logger.error(r.get("traceback"))
            stats.failed += 1
            junit_testcase.error = ("Test execution error", r.get("traceback", "Unknown error"))
            junit_registry_suite.add_testcase(junit_testcase)
            continue

        action = r.get("action", [])
        fmted_output = "\n".join(action) if action else "[NO OUTPUT]"
        expected = r.get("expected")
        Logger.info(f"INPUT: {inp}")
        if note:
            Logger.info(f"NOTE: {note}")
        Logger.info(f"OUTPUT:\n{fmted_output}")

        if isinstance(expected, Expectation):
            Logger.info(f"EXPECT: {expected}")
            match = await expected.match(r)
            if match:
                Logger.success("RESULT: PASS")
                stats.passed += 1
            elif match is False:
                Logger.error("RESULT: FAIL")
                stats.failed += 1
                junit_testcase.failure = ("Assertion failed", f"Expected: {expected}\nActual: {fmted_output}")
                junit_registry_suite.add_testcase(junit_testcase)
                continue
        else:
            if IS_CI:
                Logger.info("RESULT: SKIP (expects manual review, unavailable in CI)")
                junit_testcase.skipped = "Manual review required (unavailable in CI)"
                junit_registry_suite.add_testcase(junit_testcase)
                continue
            try:
                Logger.warning("REVIEW: Did the output meet expectations? [y/N]")
                check = input()
                if check in confirm_command:
                    Logger.success("RESULT: PASS")
                    stats.passed += 1
                else:
                    Logger.error("RESULT: FAIL")
                    stats.failed += 1
                    junit_testcase.failure = (
                        "Manual review failed",
                        f"Expected: {expected}\nActual: {fmted_output}",
                    )
                    junit_registry_suite.add_testcase(junit_testcase)
                    continue
            except (EOFError, KeyboardInterrupt):
                print("")
                Logger.warning("Interrupted by user.")
                os._exit(1)

        junit_registry_suite.add_testcase(junit_testcase)

        if tcost is not None:
            Logger.info(f"TIME COST: {tcost:.06f}s")
            stats.time_cost += tcost

    Logger.info("-" * 60)


class FuncTestResult(TypedDict):
    fn: FunctionType
    path: str
    res: dict


@dataclass
class FuncTestStats:
    total: int = 0
    passed: int = 0
    failed: int = 0
    time_cost: float = 0.0


async def _run_func_test(fn: FunctionType, path: str) -> FuncTestResult:
    Logger.trace(f"_run_func_test START: {fn.__name__} ({path})")
    res = await run_function_entry(fn, IS_CI)
    Logger.trace(f"_run_func_test DONE: {fn.__name__}")
    return {"fn": fn, "path": path, "res": res}


def _report_func_test(func_result: FuncTestResult, test_number: int, stats: FuncTestStats) -> None:
    fn = func_result["fn"]
    path = func_result["path"]
    res = func_result.get("res", {})

    Logger.info(f"TEST{test_number}: {fn.__name__} ({path})")
    if fn.__doc__:
        Logger.info(f"DOC: {fn.__doc__}")

    Logger.info("-" * 60)

    if res.get("skipped"):
        junit_testcase = JUnitTestCase(
            name=fn.__name__, classname=f"FunctionTest.{test_number}", time=res.get("time_cost", 0.0)
        )
        junit_testcase.skipped = "Test skipped"
        junit_func_suite.add_testcase(junit_testcase)
        stats.total += 1
        return
    if res.get("timeout"):
        stats.failed += 1
        stats.total += 1
        timeout_limit = res.get("timeout_limit")
        active_test = res.get("active_test")
        completed_tests = res.get("completed_tests", 0)
        detail = f"No progress for {timeout_limit} seconds after {completed_tests} completed subtests"
        if active_test:
            detail += f"\nActive subtest: {active_test}"
        if res.get("cleanup_pending"):
            detail += "\nCancellation cleanup exceeded its deadline"
        Logger.error(detail)
        junit_testcase = JUnitTestCase(
            name=fn.__name__, classname=f"FunctionTest.{test_number}", time=res.get("time_cost", 0.0)
        )
        junit_testcase.failure = ("Function test timeout", detail)
        junit_func_suite.add_testcase(junit_testcase)
        return
    if res.get("error"):
        stats.failed += 1
        stats.total += 1
        junit_testcase = JUnitTestCase(
            name=fn.__name__, classname=f"FunctionTest.{test_number}", time=res.get("time_cost", 0.0)
        )
        junit_testcase.error = ("Test error", res.get("error", "Unknown error"))
        junit_func_suite.add_testcase(junit_testcase)
        return

    entries = res["entries"]
    if not entries:
        Logger.warning(f"No inputs registered in func test {fn.__name__}; skipping.")
        junit_testcase = JUnitTestCase(
            name=fn.__name__, classname=f"FunctionTest.{test_number}", time=res.get("time_cost", 0.0)
        )
        junit_testcase.skipped = "No inputs registered"
        junit_func_suite.add_testcase(junit_testcase)
        stats.total += 1
        return

    results = res["results"]
    subtest_number = 0
    func_pass = True
    func_error_msgs: list[str] = []
    for r in results:
        type_ = r.get("type")
        note = r.get("note")
        inp = r.get("input")

        if "timeout" in r:
            if type_ == "integration":
                Logger.error(f"INPUT: {inp}")
            if note:
                Logger.error(f"NOTE: {note}")
            Logger.error("RESULT: FAIL (timeout)")
            func_pass = False
            if type_ == "integration":
                func_error_msgs.append(f"Test timeout for input: {inp}")
            else:
                func_error_msgs.append("Test timeout")
            break

        if "traceback" in r:
            if type_ == "integration":
                Logger.error(f"INPUT: {inp}")
            if note:
                Logger.error(f"NOTE: {note}")
            Logger.error("ERROR during execution:")
            Logger.error(r.get("traceback"))
            func_pass = False
            func_error_msgs.append(r.get("traceback", "Unknown error"))
            if type_ == "integration":
                break
            Logger.error("RESULT: FAIL (exception)")
            continue

        expected = r.get("expected")
        action = r.get("action", [])
        fmted_output = "\n".join(action) if action else "[NO OUTPUT]"

        if type_ == "integration":
            Logger.info(f"INPUT: {inp}")
        if note:
            Logger.info(f"NOTE: {note}")
        if type_ == "integration":
            Logger.info(f"OUTPUT:\n{fmted_output}")
        if expected is not None:
            Logger.info(f"EXPECT: {expected}")

        if r.get("match"):
            Logger.success("RESULT: PASS")
            continue
        if expected is None:
            if IS_CI:
                Logger.info("RESULT: SKIP (expects manual review, unavailable in CI)")
                continue
            try:
                Logger.warning("REVIEW: Did the output meet expectations? [y/N]")
                check = input()
                if check in confirm_command:
                    Logger.success("RESULT: PASS")
                    continue
                func_pass = False
                func_error_msgs.append(f"Manual review failed for input: {inp}")
            except (EOFError, KeyboardInterrupt):
                print("")
                Logger.warning("Interrupted by user.")
                os._exit(1)
        else:
            Logger.error("RESULT: FAIL")
            func_pass = False
            func_error_msgs.append(f"Expected: {expected}\nActual: {fmted_output}")
        break

    func_error_msg = "\n".join(func_error_msgs)
    if func_pass:
        Logger.success(f"FUNC ({fn.__name__}) RESULT: PASS")
        stats.passed += 1
        junit_testcase = JUnitTestCase(
            name=fn.__name__, classname=f"FunctionTest.{test_number}", time=res.get("time_cost", 0.0)
        )
    else:
        Logger.error(f"FUNC ({fn.__name__}) RESULT: FAIL")
        stats.failed += 1
        junit_testcase = JUnitTestCase(
            name=fn.__name__, classname=f"FunctionTest.{test_number}", time=res.get("time_cost", 0.0)
        )
        junit_testcase.failure = ("Function test failed", func_error_msg)

    junit_func_suite.add_testcase(junit_testcase)

    for failed_result in results:
        if failed_result.get("match"):
            continue
        if "traceback" not in failed_result:
            continue
        subtest_number += 1
        subtest_name = failed_result.get("note") or getattr(
            failed_result.get("expected"), "__name__", str(failed_result.get("expected"))
        )
        junit_subtest = JUnitTestCase(
            name=f"{fn.__name__}::{subtest_name}",
            classname=f"FunctionTest.{test_number}.{subtest_number}",
            time=res.get("time_cost", 0.0),
        )
        if failed_result.get("type") == "integration":
            junit_subtest.error = ("Test execution error", failed_result.get("traceback", "Unknown error"))
        else:
            junit_subtest.failure = (
                f"Subtest raised {failed_result.get('exception_type', 'Exception')}",
                failed_result.get("traceback", "Unknown error"),
            )
        junit_func_suite.add_testcase(junit_subtest)

    tcost = res.get("time_cost")
    if tcost is not None:
        Logger.info(f"TIME COST: {tcost:.06f}s")
        stats.time_cost += tcost

    stats.total += 1
    Logger.info("-" * 60)


def _iter_integration_files() -> list[str]:
    """列出待运行的整合测试文件，AKARI_TEST_FILTER 可按路径子串筛选。"""
    pattern = str(INTEGRATION_TESTS_PATH / "**" / "*.py")
    files = [
        path for path in sorted(glob.glob(pattern, recursive=True)) if not os.path.basename(path).startswith(("_", "."))
    ]
    selector = os.environ.get(TEST_FILTER_ENV, "").strip().replace("\\", "/")
    if selector:
        files = [path for path in files if selector in path.replace("\\", "/")]
    return files


async def main(inspect_module=inspect):
    Logger.trace("main() START")

    cache_path.mkdir(parents=True, exist_ok=True)

    Logger.trace("main() init_db")
    try:
        if not await init_db():
            Logger.critical(f"Failed to initialize database. Aborting tests.\n{get_last_init_error()}")
            await close_db()
            return 1
    except Exception:
        Logger.exception()
        await close_db()
        return 1

    Logger.trace("main() load_modules")
    try:
        await load_modules(monkey_patches={"Random": Random()})
    except Exception:
        Logger.exception("Failed to load modules for tests:")
        await close_db()
        return 1

    Logger.trace("main() get_registry")
    Logger.info(ascii_art)
    Logger.info("=" * 60)
    Logger.info("Tester is running. Please wait...")
    Logger.info("=" * 60)
    registry = get_registry()
    Logger.trace(f"main() registry has {len(registry)} entries")

    total = 0
    passed = 0
    failed = 0
    total_test_cost = 0.0
    force_exit = False

    registry_stats = RegistryTestStats()
    for idx, entry in enumerate(registry, 1):
        try:
            reg_result = await _run_registry_entry(entry, idx)
        except Exception as e:
            reg_result = e
        await _report_registry_case(entry, reg_result, idx, registry_stats)
    total += registry_stats.total
    passed += registry_stats.passed
    failed += registry_stats.failed
    total_test_cost += registry_stats.time_cost

    Logger.trace("main() starting func tests discovery")
    func_tasks: list[tuple[FunctionType, str]] = []
    if INTEGRATION_TESTS_PATH.is_dir():
        pyfiles = _iter_integration_files()
        Logger.trace(f"main() found {len(pyfiles)} test files")

        for path in pyfiles:
            name = os.path.splitext(os.path.basename(path))[0]
            Logger.trace(f"main() importing {path}")
            spec = importlib.util.spec_from_file_location(f"tests_{name}", path)
            if not spec or not spec.loader:
                message = f"Failed resolving tests file {path}."
                Logger.error(message)
                failed += 1
                total += 1
                junit_testcase = JUnitTestCase(name=Path(path).name, classname="TestCollection")
                junit_testcase.error = ("Test file resolution error", message)
                junit_func_suite.add_testcase(junit_testcase)
                continue
            mod = importlib.util.module_from_spec(spec)
            try:
                sys.modules[spec.name] = mod
                spec.loader.exec_module(mod)
            except Exception:
                import_error = traceback.format_exc()
                Logger.exception(f"Failed importing tests file {path}:")
                failed += 1
                total += 1
                junit_testcase = JUnitTestCase(name=Path(path).name, classname="TestCollection")
                junit_testcase.error = ("Test file import error", import_error)
                junit_func_suite.add_testcase(junit_testcase)
                continue

            for _, fn in inspect_module.getmembers(mod, inspect_module.isfunction):
                if not getattr(fn, "_func_case", False):
                    continue

                Logger.trace(f"main() found func_case: {fn.__name__} in {path}")
                func_tasks.append((fn, path))

        Logger.trace(f"main() running {len(func_tasks)} func tests sequentially")
        func_stats = FuncTestStats()
        for idx, (fn, path) in enumerate(func_tasks, 1):
            Logger.trace(f"main() about to run func test: {fn.__name__}")
            try:
                func_result = await _run_func_test(fn, path)
            except Exception as e:
                Logger.error(f"main() EXCEPTION running func test {fn.__name__}: {e}")
                func_result = {"fn": fn, "path": path, "res": {"error": repr(e)}}
            # 每个入口跑完立即汇报，长跑时不必等全部用例结束才有输出。
            _report_func_test(func_result, len(registry) + idx, func_stats)
            Logger.trace(f"main() finished func test: {fn.__name__}")
            if func_result["res"].get("cleanup_pending"):
                force_exit = True
                Logger.error(f"Stopping after {fn.__name__}: timed-out task did not finish cancellation cleanup.")
                break
        passed += func_stats.passed
        failed += func_stats.failed
        total += func_stats.total
        total_test_cost += func_stats.time_cost
        Logger.trace(f"main() all func tests completed, counted {func_stats.total} entries")
    Logger.trace("main() all tests processed")
    if total > 0:
        Logger.info(f"TOTAL: {total}")
        if passed:
            Logger.success(f"PASSED: {passed}")
        if failed:
            Logger.error(f"FAILED: {failed}")
        Logger.info(f"TIME COST: {total_test_cost:.06f}s")
        Logger.info("=" * 60)
    else:
        Logger.warning("No tests registered. Use `core.tester.func_case` to register integration tests.")

    if IS_CI:
        try:
            junit_report.add_testsuite(junit_registry_suite)
            if junit_func_suite.test_cases:
                junit_report.add_testsuite(junit_func_suite)

            junit_output_path = Path("junit.xml")
            junit_report.write_to_file(junit_output_path)
            Logger.success(f"JUnit XML report generated: {junit_output_path}")
        except Exception as e:
            Logger.error(f"Failed to generate JUnit XML report: {e}")

    if force_exit:
        Logger.error("Forcing tester shutdown because a timed-out task is still running.")
        cleanup_test_environment()
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(1)

    if _coverage_instance:
        try:
            _coverage_instance.stop()
            _coverage_instance.save()

            Logger.info("=" * 60)
            Logger.info("Coverage Report:")
            _coverage_instance.report(show_missing=True)

            html_dir = Path("htmlcov")
            _coverage_instance.html_report(directory=str(html_dir))
            Logger.success(f"HTML coverage report generated: {html_dir}/index.html")

            if IS_CI:
                _coverage_instance.xml_report(outfile="coverage.xml")
                Logger.success("XML coverage report generated: coverage.xml")
        except Exception as e:
            Logger.error(f"Failed to generate coverage report: {e}")

    Logger.trace("main() close_db")
    await close_db()

    Logger.trace("main() END")
    return 1 if IS_CI and (failed > 0 or total == 0) else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
