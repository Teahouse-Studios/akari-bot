import os
import asyncio
import traceback

from tortoise import Tortoise
from tortoise.exceptions import ConfigurationError

from core.builtins.utils import confirm_command
from core.constants import FinishedException
from core.database import init_db
from core.unit_test import get_registry
from core.unit_test.session import TestMessageSession
from core.unit_test.logger import Logger
from core.unit_test.parser import parser
from core.loader import load_modules


async def _run_entry(entry: dict):
    func = entry["func"]
    input_ = entry["input"]

    results = []
    msg = TestMessageSession(input_)
    await msg.async_init(input_)
    setattr(msg, "_unittest_target", func)
    try:
        await parser(msg)
    except FinishedException:
        pass
    except Exception:
        tb = traceback.format_exc()
        results.append({"input": input_, "error": tb, "output": msg.sent, "action": msg.action})
        return results

    results.append({"input": input_, "output": msg.sent, "action": msg.action})
    return results


def main():
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

    try:
        loop.run_until_complete(load_modules())
    except Exception:
        Logger.error("Failed to load modules for tests:")
        Logger.error(traceback.format_exc())

    registry = get_registry()
    if not registry:
        Logger.error("No tests registered. Use `core.unittest.case` to register tests.")
        try:
            loop.run_until_complete(Tortoise.close_connections())
        except ConfigurationError:
            pass
        return

    i = 0
    total = 0
    passed = 0
    failed = 0

    for entry in registry:
        i += 1
        print("-" * 60)
        fn = entry["func"]
        note = entry.get("note")
        Logger.info(f"TEST{i}: {fn.__name__}  ({entry.get("file")}:{entry.get("line")})")
        results = loop.run_until_complete(_run_entry(entry))

        for r in results:
            total += 1
            if "error" in r:
                Logger.error(f"INPUT: {r["input"]}")
                if note:
                    Logger.error(f"NOTE: {note}")
                Logger.error("ERROR during execution:")
                Logger.error(r["error"])
                continue

            output = r.get("output", [])
            action = r.get("action", [])
            fmted_output = "\n".join(action) if action else "[NO OUTPUT]"
            expected = entry.get("expected")
            Logger.info(f"INPUT: {r["input"]}")
            if note:
                Logger.info(f"NOTE: {note}")
            Logger.info(f"OUTPUT:\n{fmted_output}")

            if expected is None:
                try:
                    Logger.warning("REVIEW: Did the output meet expectations? [y/N]")
                    check = input()
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
                ...
                """
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
                """
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
