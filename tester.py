from core import check_python_version

check_python_version()  # noqa

import asyncio
import glob
import importlib.util
import inspect
import os
import sys

from core.builtins.utils import confirm_command
from core.constants import cache_path, tests_path
from core.logger import Logger
from core.tester.decorator import get_registry
from core.tester.expectations import Expectation
from core.tester.mock.database import init_db, close_db
from core.tester.mock.loader import load_modules
from core.tester.mock.random import Random
from core.tester.process import run_case_entry, run_function_entry

IS_CI = os.environ.get("CI", "0") == "1"


async def main():
    Logger.rename("test", export=False)
    cache_path.mkdir(parents=True, exist_ok=True)

    try:
        if not await init_db():
            Logger.critical("Failed to initialize database. Aborting tests.")
            await close_db()
            return
    except Exception:
        Logger.exception()
        await close_db()
        return
    try:
        await load_modules(monkey_patches={"Random": Random()})
    except Exception:
        Logger.exception("Failed to load modules for tests:")

    print("=" * 60)
    registry = get_registry()

    i = 0
    total = 0
    passed = 0
    failed = 0
    total_test_cost = 0.0

    for entry in registry:
        i += 1
        print("-" * 60)
        fn = entry["func"]
        note = entry.get("note") or (fn.__doc__ if fn.__doc__ else None)
        file_loc = f"{entry.get('file')}:{entry.get('line')}"
        Logger.info(f"TEST{i}: {fn.__name__} ({file_loc})")
        if fn.__doc__:
            Logger.info(f"DOC: {fn.__doc__}")

        try:
            await close_db()
        except Exception:
            Logger.exception("Error closing database before test")
        if not await init_db():
            Logger.critical(f"Failed to reinitialize database for TEST{i}. Skipping tests.")
            continue

        try:
            await load_modules(show_logs=False, monkey_patches={"Random": Random()})
        except Exception:
            Logger.exception("Failed to load modules for tests:")

        results = await run_case_entry(entry, IS_CI)

        for r in results:
            total += 1
            inp = r.get("input")

            if "traceback" in r:
                Logger.error(f"INPUT: {inp}")
                if note:
                    Logger.error(f"NOTE: {note}")
                Logger.error("ERROR during execution:")
                Logger.error(r.get("traceback"))
                failed += 1
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
                    passed += 1
                elif match is False:
                    Logger.error("RESULT: FAIL")
                    failed += 1
            else:
                if IS_CI:
                    Logger.error("RESULT: FAIL (expects manual review, unavailable in CI)")
                    failed += 1
                else:
                    try:
                        Logger.warning("REVIEW: Did the output meet expectations? [y/N]")
                        check = input()
                        if check in confirm_command:
                            Logger.success("RESULT: PASS")
                            passed += 1
                        else:
                            Logger.error("RESULT: FAIL")
                            failed += 1
                    except (EOFError, KeyboardInterrupt):
                        print("")
                        Logger.warning("Interrupted by user.")
                        os._exit(1)
            tcost = r.get("time_cost")
            if tcost is not None:
                Logger.info(f"TIME COST: {tcost:.06f}s")
                total_test_cost += tcost
        print("-" * 60)

    if os.path.isdir(tests_path):
        pyfiles = sorted(glob.glob(os.path.join(tests_path, "*.py")))
        for path in pyfiles:
            name = os.path.splitext(os.path.basename(path))[0]
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
                i += 1
                Logger.info(f"TEST{i}: {fn.__name__} ({path})")
                if fn.__doc__:
                    Logger.info(f"DOC: {fn.__doc__}")

                res = await run_function_entry(fn, IS_CI)
                if res.get("skipped"):
                    continue
                if res.get("error"):
                    failed += 1
                    total += 1
                    continue

                entries = res["entries"]
                if not entries:
                    Logger.warning(f"No inputs registered in func test {fn.__name__}; skipping.")
                    continue

                results = res["results"]

                func_pass = True
                for r in results:
                    note = r.get("note")
                    inp = r.get("input")

                    if "traceback" in r:
                        Logger.error(f"INPUT: {inp}")
                        if note:
                            Logger.error(f"NOTE: {note}")
                        Logger.error("ERROR during execution:")
                        Logger.error(r.get("traceback"))
                        func_pass = False
                        break

                    expected = r.get("expected")
                    action = r.get("action", [])
                    fmted_output = "\n".join(action) if action else "[NO OUTPUT]"

                    Logger.info(f"INPUT: {inp}")
                    if note:
                        Logger.info(f"NOTE: {note}")
                    Logger.info(f"OUTPUT:\n{fmted_output}")

                    if expected is not None:
                        Logger.info(f"EXPECT: {expected}")

                    if r.get("match"):
                        Logger.success("RESULT: PASS")
                        continue
                    if expected is None:
                        try:
                            Logger.warning("REVIEW: Did the output meet expectations? [y/N]")
                            check = input()
                            if check in confirm_command:
                                Logger.success("RESULT: PASS")
                                continue
                            func_pass = False
                        except (EOFError, KeyboardInterrupt):
                            print("")
                            Logger.warning("Interrupted by user.")
                            os._exit(1)
                    else:
                        Logger.error("RESULT: FAIL")
                    func_pass = False
                    break

                if func_pass:
                    Logger.success(f"FUNC ({fn.__name__}) RESULT: PASS")
                    passed += 1
                else:
                    Logger.error(f"FUNC ({fn.__name__}) RESULT: FAIL")
                    failed += 1

                tcost = res.get("time_cost")
                if tcost is not None:
                    Logger.info(f"TIME COST: {tcost:.06f}s")
                    total_test_cost += tcost

                total += 1
                print("-" * 60)

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
    await close_db()

    if IS_CI and failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
