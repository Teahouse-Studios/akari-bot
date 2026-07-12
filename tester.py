from core import check_python_version  # skipcq

check_python_version()  # noqa

import asyncio
import glob
import importlib.util
import inspect
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from core.builtins.utils import confirm_command
from core.constants import ascii_art, cache_path, tests_path
from core.logger import Logger
from core.tester.decorator import get_registry
from core.tester.expectations import Expectation
from core.tester.junit import JUnitReport, JUnitTestSuite, JUnitTestCase
from core.tester.mock.database import init_db, close_db
from core.tester.mock.loader import load_modules
from core.tester.mock.random import Random
from core.tester.process import run_case_entry, run_function_entry


load_dotenv()
os.environ.setdefault("PYTHONIOENCODING", "UTF-8")
os.environ.setdefault("PYTHONPATH", str(Path(".").resolve()))

IS_CI = os.environ.get("CI", "0") == "1"
ENABLE_COVERAGE = os.environ.get("COVERAGE", "0") == "1"
MAX_CONCURRENT = 10

# Coverage 集成
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


async def _run_registry_entry(semaphore: asyncio.Semaphore, entry: dict, test_number: int) -> dict:
    Logger.trace(f"_run_registry_entry START: TEST{test_number}")
    async with semaphore:
        Logger.trace(f"_run_registry_entry ACQUIRED semaphore: TEST{test_number}")
        fn = entry["func"]
        note = entry.get("note") or (fn.__doc__ if fn.__doc__ else None)
        file_loc = f"{entry.get('file')}:{entry.get('line')}"
        Logger.info(f"TEST{test_number}: {fn.__name__} ({file_loc})")
        if fn.__doc__:
            Logger.info(f"DOC: {fn.__doc__}")

        Logger.trace(f"_run_registry_entry close_db: TEST{test_number}")
        try:
            await close_db()
        except Exception:
            Logger.exception("Error closing database before test")
        Logger.trace(f"_run_registry_entry init_db: TEST{test_number}")
        if not await init_db():
            Logger.critical(f"Failed to reinitialize database for TEST{test_number}. Skipping tests.")
            return {"test_number": test_number, "skipped": True, "note": note}

        Logger.trace(f"_run_registry_entry load_modules: TEST{test_number}")
        try:
            await load_modules(show_logs=False, monkey_patches={"Random": Random()})
        except Exception:
            Logger.exception("Failed to load modules for tests:")

        Logger.trace(f"_run_registry_entry run_case_entry: TEST{test_number}")
        results = await run_case_entry(entry, IS_CI)
        Logger.trace(f"_run_registry_entry DONE: TEST{test_number}")
        return {"test_number": test_number, "results": results, "note": note}


async def _run_func_test(fn, path) -> dict:
    Logger.trace(f"_run_func_test START: {fn.__name__} ({path})")
    res = await run_function_entry(fn, IS_CI)
    Logger.trace(f"_run_func_test DONE: {fn.__name__}")
    return {"fn": fn, "path": path, "res": res}


async def main():
    Logger.trace("main() START")

    Logger.rename("test", export=False)
    cache_path.mkdir(parents=True, exist_ok=True)
    Logger.info(ascii_art)

    Logger.trace("main() init_db")
    try:
        if not await init_db():
            Logger.critical("Failed to initialize database. Aborting tests.")
            await close_db()
            return
    except Exception:
        Logger.exception()
        await close_db()
        return

    Logger.trace("main() load_modules")
    try:
        await load_modules(monkey_patches={"Random": Random()})
    except Exception:
        Logger.exception("Failed to load modules for tests:")

    Logger.trace("main() get_registry")
    print("=" * 60)
    registry = get_registry()
    Logger.trace(f"main() registry has {len(registry)} entries")

    test_number = 0
    total = 0
    passed = 0
    failed = 0
    total_test_cost = 0.0

    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    registry_tasks = []

    Logger.trace("main() creating registry tasks")
    for idx, entry in enumerate(registry, 1):
        task = _run_registry_entry(semaphore, entry, idx)
        registry_tasks.append(task)

    Logger.trace(f"main() gathering {len(registry_tasks)} registry tasks")
    registry_results = await asyncio.gather(*registry_tasks, return_exceptions=True)
    Logger.trace(f"main() registry tasks completed, got {len(registry_results)} results")

    for reg_result in registry_results:
        if isinstance(reg_result, Exception):
            Logger.error(f"Error during test execution: {reg_result}")
            Logger.trace(f"main() EXCEPTION in registry result: {reg_result}")
            continue

        if not isinstance(reg_result, dict):
            Logger.trace(f"main() non-dict result: {type(reg_result)}")
            continue

        print("-" * 60)

        if reg_result.get("skipped"):
            Logger.trace("main() skipped result")
            continue

        test_number = reg_result.get("test_number")
        note = reg_result.get("note")
        results = reg_result.get("results", [])
        Logger.trace(f"main() processing TEST{test_number} with {len(results)} results")

        for r in results:
            total += 1
            inp = r.get("input")
            tcost = r.get("time_cost", 0.0)
            test_case_name = f"TEST{test_number}_{total}"
            junit_testcase = JUnitTestCase(
                name=test_case_name, classname=f"RegistryTest.{test_number}", time=tcost if tcost else 0.0
            )

            if "timeout" in r:
                Logger.error(f"INPUT: {inp}")
                if note:
                    Logger.error(f"NOTE: {note}")
                Logger.error("RESULT: FAIL (timeout)")
                failed += 1
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
                failed += 1
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
                Logger.trace(f"main() matching expectation for TEST{test_number}")
                match = await expected.match(r)
                Logger.trace(f"main() match result: {match}")
                if match:
                    Logger.success("RESULT: PASS")
                    passed += 1
                elif match is False:
                    Logger.error("RESULT: FAIL")
                    failed += 1
                    junit_testcase.failure = ("Assertion failed", f"Expected: {expected}\nActual: {fmted_output}")
                    junit_registry_suite.add_testcase(junit_testcase)
                    continue
            else:
                if IS_CI:
                    Logger.info("RESULT: SKIP (expects manual review, unavailable in CI)")
                    junit_testcase.skipped = "Manual review required (unavailable in CI)"
                    junit_registry_suite.add_testcase(junit_testcase)
                    continue
                else:
                    Logger.trace(
                        f"main() MANUAL REVIEW required for TEST{test_number} - this will HANG in non-CI mode!"
                    )
                    try:
                        Logger.warning("REVIEW: Did the output meet expectations? [y/N]")
                        check = input()
                        if check in confirm_command:
                            Logger.success("RESULT: PASS")
                            passed += 1
                        else:
                            Logger.error("RESULT: FAIL")
                            failed += 1
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
                total_test_cost += tcost
        print("-" * 60)

    Logger.trace("main() starting func tests discovery")
    if os.path.isdir(tests_path):
        pyfiles = sorted(glob.glob(os.path.join(tests_path, "**", "*.py"), recursive=True))
        Logger.trace(f"main() found {len(pyfiles)} test files")
        func_tasks = []
        func_info_list = []

        for path in pyfiles:
            name = os.path.splitext(os.path.basename(path))[0]
            Logger.trace(f"main() importing {path}")
            spec = importlib.util.spec_from_file_location(f"tests_{name}", path)
            mod = importlib.util.module_from_spec(spec)
            try:
                sys.modules[spec.name] = mod
                spec.loader.exec_module(mod)
            except Exception:
                Logger.exception(f"Failed importing tests file {path}:")
                continue

            for _, fn in inspect.getmembers(mod, inspect.isfunction):
                if not getattr(fn, "_func_case", False):
                    continue

                Logger.trace(f"main() found func_case: {fn.__name__} in {path}")
                func_tasks.append((fn, path))
                func_info_list.append((len(func_tasks) - 1, len(registry) + len(func_info_list) + 1))

        Logger.trace(f"main() running {len(func_tasks)} func tests sequentially")
        func_results = []
        for fn, path in func_tasks:
            Logger.trace(f"main() about to run func test: {fn.__name__}")
            try:
                result = await _run_func_test(fn, path)
                func_results.append(result)
            except Exception as e:
                Logger.error(f"main() EXCEPTION running func test {fn.__name__}: {e}")
                func_results.append(e)
            Logger.trace(f"main() finished func test: {fn.__name__}")
        Logger.trace(f"main() all func tests completed, got {len(func_results)} results")

        for idx, func_result in enumerate(func_results):
            Logger.trace(f"main() processing func result {idx}/{len(func_results)}")
            if isinstance(func_result, Exception):
                Logger.error(f"Error during function test execution: {func_result}")
                Logger.trace(f"main() EXCEPTION in func result: {func_result}")
                continue

            if not isinstance(func_result, dict):
                Logger.trace(f"main() non-dict func result at index {idx}")
                continue

            fn = func_result.get("fn")
            path = func_result.get("path")
            res = func_result.get("res", {})

            test_number = len(registry) + idx + 1

            Logger.info(f"TEST{test_number}: {fn.__name__} ({path})")
            if fn.__doc__:
                Logger.info(f"DOC: {fn.__doc__}")

            print("-" * 60)

            if res.get("skipped"):
                Logger.trace(f"main() func test {fn.__name__} skipped")
                junit_testcase = JUnitTestCase(
                    name=fn.__name__, classname=f"FunctionTest.{test_number}", time=res.get("time_cost", 0.0)
                )
                junit_testcase.skipped = "Test skipped"
                junit_func_suite.add_testcase(junit_testcase)
                continue
            if res.get("error"):
                Logger.trace(f"main() func test {fn.__name__} has error")
                failed += 1
                total += 1
                junit_testcase = JUnitTestCase(
                    name=fn.__name__, classname=f"FunctionTest.{test_number}", time=res.get("time_cost", 0.0)
                )
                junit_testcase.error = ("Test error", res.get("error", "Unknown error"))
                junit_func_suite.add_testcase(junit_testcase)
                continue

            entries = res["entries"]
            if not entries:
                Logger.warning(f"No inputs registered in func test {fn.__name__}; skipping.")
                Logger.trace(f"main() func test {fn.__name__} has no entries")
                junit_testcase = JUnitTestCase(
                    name=fn.__name__, classname=f"FunctionTest.{test_number}", time=res.get("time_cost", 0.0)
                )
                junit_testcase.skipped = "No inputs registered"
                junit_func_suite.add_testcase(junit_testcase)
                continue

            results = res["results"]
            Logger.trace(f"main() processing func test {fn.__name__} with {len(results)} results")

            func_pass = True
            func_error_msg = ""
            for r_idx, r in enumerate(results):
                Logger.trace(f"main() processing result {r_idx}/{len(results)} for {fn.__name__}")
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
                        func_error_msg = f"Test timeout for input: {inp}"
                    else:
                        func_error_msg = "Test timeout"
                    break

                if "traceback" in r:
                    if type_ == "integration":
                        Logger.error(f"INPUT: {inp}")
                    if note:
                        Logger.error(f"NOTE: {note}")
                    Logger.error("ERROR during execution:")
                    Logger.error(r.get("traceback"))
                    func_pass = False
                    func_error_msg = r.get("traceback", "Unknown error")
                    break

                expected = r.get("expected")
                action = r.get("action", [])
                fmted_output = "\n".join(action) if action else "[NO OUTPUT]"

                Logger.trace(f"main() checking result: expected={expected}, match={r.get('match')}")
                if type_ == "integration":
                    Logger.info(f"INPUT: {inp}")
                if note:
                    Logger.info(f"NOTE: {note}")
                if type_ == "integration":
                    Logger.info(f"OUTPUT:\n{fmted_output}")

                if expected is not None:
                    Logger.info(f"EXPECT: {expected}")

                if r.get("match"):
                    Logger.trace("main() match is truthy, PASS")
                    Logger.success("RESULT: PASS")
                    continue
                Logger.trace("main() match is falsy or None, checking expected...")
                if expected is None:
                    if IS_CI:
                        Logger.info("RESULT: SKIP (expects manual review, unavailable in CI)")
                        continue
                    Logger.trace(f"main() MANUAL REVIEW required for func test {fn.__name__} - this will HANG!")
                    try:
                        Logger.warning("REVIEW: Did the output meet expectations? [y/N]")
                        check = input()
                        if check in confirm_command:
                            Logger.success("RESULT: PASS")
                            continue
                        func_pass = False
                        func_error_msg = f"Manual review failed for input: {inp}"
                    except (EOFError, KeyboardInterrupt):
                        print("")
                        Logger.warning("Interrupted by user.")
                        os._exit(1)
                else:
                    Logger.error("RESULT: FAIL")
                    func_pass = False
                    func_error_msg = f"Expected: {expected}\nActual: {fmted_output}"
                break

            if func_pass:
                Logger.success(f"FUNC ({fn.__name__}) RESULT: PASS")
                passed += 1
                junit_testcase = JUnitTestCase(
                    name=fn.__name__, classname=f"FunctionTest.{test_number}", time=res.get("time_cost", 0.0)
                )
            else:
                Logger.error(f"FUNC ({fn.__name__}) RESULT: FAIL")
                failed += 1
                junit_testcase = JUnitTestCase(
                    name=fn.__name__, classname=f"FunctionTest.{test_number}", time=res.get("time_cost", 0.0)
                )
                junit_testcase.failure = ("Function test failed", func_error_msg)

            junit_func_suite.add_testcase(junit_testcase)

            tcost = res.get("time_cost")
            if tcost is not None:
                Logger.info(f"TIME COST: {tcost:.06f}s")
                total_test_cost += tcost

            total += 1
            print("-" * 60)

    Logger.trace("main() all tests processed")
    if total > 0:
        Logger.info(f"TOTAL: {total}")
        if passed:
            Logger.success(f"PASSED: {passed}")
        if failed:
            Logger.error(f"FAILED: {failed}")
        Logger.info(f"TIME COST: {total_test_cost:.06f}s")
        print("=" * 60)
    else:
        Logger.warning("No tests registered. Use `core.tester.case` or `core.tester.test_case` to register tests.")

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

    # Coverage 报告生成
    if _coverage_instance:
        try:
            _coverage_instance.stop()
            _coverage_instance.save()

            # 生成控制台报告
            Logger.info("=" * 60)
            Logger.info("Coverage Report:")
            _coverage_instance.report(show_missing=True)

            # 生成 HTML 报告
            html_dir = Path("htmlcov")
            _coverage_instance.html_report(directory=str(html_dir))
            Logger.success(f"HTML coverage report generated: {html_dir}/index.html")

            # 生成 XML 报告（可选，用于 CI 集成）
            if IS_CI:
                _coverage_instance.xml_report(outfile="coverage.xml")
                Logger.success("XML coverage report generated: coverage.xml")
        except Exception as e:
            Logger.error(f"Failed to generate coverage report: {e}")

    Logger.trace("main() close_db")
    await close_db()

    Logger.trace("main() END")
    if IS_CI and failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
