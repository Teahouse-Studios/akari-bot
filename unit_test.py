import os
import sys
import asyncio
import importlib.util
import traceback
from typing import List

from tortoise import Tortoise
from tortoise.exceptions import ConfigurationError

from core.builtins.utils import confirm_command
from core.constants import FinishedException
from core.database import init_db
from core.unit_test import get_registry
from core.unit_test.session import TestMessageSession
from core.unit_test.logger import Logger
from core.unit_test.parser import parser


async def _run_entry(entry: dict):
    func = entry["func"]
    input_ = entry["input"]
    note = entry.get("note")

    results = []
    msg = TestMessageSession(input_)
    await msg.async_init()
    # 告知 parser 測試期望的目標函數，parser 在單元測試模式下會僅執行此函數
    setattr(msg, "_unittest_target", func)
    try:
        await parser(msg)
    except FinishedException:
        pass
    except Exception:
        tb = traceback.format_exc()
        results.append({"input": input_, "error": tb, "output": msg.sent_msg, "action": msg.action, "note": note})
        return results

    results.append({"input": input_, "output": msg.sent_msg, "action": msg.action, "note": note})
    return results


def discover_and_import(paths: List[str]):
    for p in paths:
        if not os.path.exists(p):
            continue
        if os.path.isdir(p):
            for root, _, files in os.walk(p):
                for f in files:
                    if f.endswith(".py"):
                        import_file(os.path.join(root, f))
        elif p.endswith(".py"):
            import_file(p)


def import_file(path: str):
    try:
        name = os.path.splitext(os.path.basename(path))[0]
        spec = importlib.util.spec_from_file_location(f"unittest_imports.{name}", path)
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
    except ModuleNotFoundError:
        pass
    except Exception:
        Logger.error(f"Failed to import {path}:", file=sys.stderr)
        Logger.error(traceback.format_exc())


def main():
    paths = ["modules"]
    abs_paths = [os.path.join(os.getcwd(), p) for p in paths]
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        init_success = loop.run_until_complete(init_db())
        if not init_success:
            Logger.critical("Failed to initialize database. Aborting tests.")
            try:
                loop.run_until_complete(Tortoise.close_connections())
            except ConfigurationError:
                pass
            return
    except Exception:
        Logger.error(traceback.format_exc())
        try:
            loop.run_until_complete(Tortoise.close_connections())
        except ConfigurationError:
            pass
        return

    discover_and_import(abs_paths)

    registry = get_registry()
    if not registry:
        Logger.error("No tests registered. Use `core.unittest.case` to register tests.")
        try:
            loop.run_until_complete(Tortoise.close_connections())
        except ConfigurationError:
            pass
        return

    total = 0
    passed = 0
    failed = 0

    for entry in registry:
        print("-" * 60)
        fn = entry["func"]
        Logger.info(f"TEST: {fn.__name__}  ({entry.get('file')}:{entry.get('line')})")
        results = loop.run_until_complete(_run_entry(entry))

        for r in results:
            total += 1
            if "error" in r:
                Logger.error(f"INPUT: {r['input']}")
                Logger.error(f"NOTE: {r['note']}")
                Logger.error("ERROR during execution:")
                Logger.error(r["error"])
                continue

            output = r.get("output", [])
            action = r.get("action", [])
            fmted_output = "\n".join(action) if action else "[NO OUTPUT]"
            expected = entry.get("expected")
            Logger.info(f"INPUT: {r["input"]}")
            Logger.info(f"NOTE: {r['note']}")
            Logger.info(f"OUTPUT:\n{fmted_output}")

            if expected is None:
                try:
                    check = input("Did the output meet expectations? [Y/n]: ")
                    if check in confirm_command:
                        Logger.success("RESULT: PASS")
                        passed += 1
                    else:
                        Logger.error("RESULT: FAIL")
                        failed += 1
                except KeyboardInterrupt:
                    print("")
                    Logger.warning("Interrupted by user.")
                    os._exit(1)
            else:
                ok = False
                if isinstance(expected, list):
                    ok = expected == output
                else:
                    joined = "\n".join(map(str, output))
                    ok = str(expected) == joined or (len(output) == 1 and str(expected) == str(output[0]))

                if ok:
                    Logger.success("RESULT: PASS")
                    passed += 1
                else:
                    Logger.error("RESULT: FAIL")
                    Logger.error("EXPECTED:", expected)
                    failed += 1
        print("-" * 60)
    Logger.info(f"TOTAL: {total}")
    if passed:
        Logger.success(f"PASSED: {passed}")
    if failed:
        Logger.error(f"FAILED: {failed}")
    print("-" * 60)

    try:
        loop.run_until_complete(Tortoise.close_connections())
    except ConfigurationError:
        pass


if __name__ == "__main__":
    main()
