import asyncio
import os

from core.builtins.message.chain import MessageChain
from core.builtins.message.elements import PlainElement
from core.builtins.session.info import SessionInfo
from core.builtins.utils import confirm_command
from core.logger import Logger
from core.tester import get_registry, run_registry
from core.tester.mock.database import init_db, close_db
from core.tester.mock.loader import load_modules
from core.tester.mock.random import Random


async def main():
    Logger.rename("test", export=False)
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

    registry = get_registry()
    if not registry:
        Logger.error("No tests registered. Use `core.casetest.case` to register tests.")
        await close_db()
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
        Logger.info(f"TEST{i}: {fn.__name__}  ({entry.get('file')}:{entry.get('line')})")

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

        results = await run_registry(entry)

        for r in results:
            total += 1
            if "error" in r:
                Logger.error(f"INPUT: {r["input"]}")
                if note:
                    Logger.error(f"NOTE: {note}")
                Logger.error("ERROR during execution:")
                Logger.error(r["error"])
                failed += 1
                continue

            output = r.get("output", [])
            action = r.get("action", [])
            fmted_output = "\n".join(action) if action else "[NO OUTPUT]"
            expected = entry.get("expected")
            Logger.info(f"INPUT: {r["input"]}")
            if note:
                Logger.info(f"NOTE: {note}")
            Logger.info(f"OUTPUT:\n{fmted_output}")

            if entry.get("manual"):
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
            elif expected is True:
                if output:
                    Logger.success("RESULT: PASS")
                    passed += 1
                else:
                    Logger.error("RESULT: FAIL")
                    failed += 1
            elif expected in (False, None):
                if not output:
                    Logger.success("RESULT: PASS")
                    passed += 1
                else:
                    Logger.error("RESULT: FAIL")
                    Logger.error("EXPECTED:\n[NO OUTPUT]")
                    failed += 1
            else:
                session_info = await SessionInfo.assign(
                    target_id="TEST|Console|0",
                    client_name="TEST",
                    target_from="TEST",
                    sender_id="TEST|0",
                    sender_from="TEST"
                )
                expected = MessageChain.assign(expected).as_sendable(session_info)
                excepted_ = "\n".join([x.text if isinstance(x, PlainElement) else str(x) for x in expected])

                if output == expected:
                    Logger.success("RESULT: PASS")
                    passed += 1
                else:
                    Logger.error("RESULT: FAIL")
                    Logger.error(f"EXPECTED:\n{excepted_}")
                    failed += 1
        print("-" * 60)
    Logger.info(f"TOTAL: {total}")
    if passed:
        Logger.success(f"PASSED: {passed}")
    if failed:
        Logger.error(f"FAILED: {failed}")
    print("-" * 60)
    await close_db()


if __name__ == "__main__":
    asyncio.run(main())
