import asyncio
import os
import traceback

from core.builtins.message.chain import MessageChain, match_kecode
from core.builtins.message.elements import PlainElement
from core.builtins.session.info import SessionInfo
from core.builtins.utils import confirm_command
from core.constants.exceptions import AbuseWarning, FinishedException, NoReportException, TestException
from core.database import init_db, close_db
from core.loader import load_modules
from core.unit_test import get_registry
from core.unit_test.session import TestMessageSession
from core.unit_test.logger import Logger
from core.unit_test.parser import parser


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
    except (AbuseWarning, NoReportException, TestException) as e:
        err_msg = msg.session_info.locale.t_str(str(e))
        err_msg_chain = match_kecode(err_msg, disable_joke=True)
        err_action = [x.text if isinstance(x, PlainElement) else str(x)
                      for x in err_msg_chain.as_sendable(msg.session_info)]
        results.append({"input": input_, "output": err_msg_chain, "action": [
                       f"(raise {type(e).__name__})"] + err_action})
        return results
    except Exception:
        tb = traceback.format_exc()
        results.append({"input": input_, "error": tb})
        return results

    results.append({"input": input_, "output": msg.sent, "action": msg.action})
    return results


async def main():
    try:
        init_success = await init_db()
        if not init_success:
            Logger.critical("Failed to initialize database. Aborting tests.")
            await close_db()
            return
    except Exception:
        Logger.error(traceback.format_exc())
        await close_db()
        return

    try:
        await load_modules()
    except Exception:
        Logger.error("Failed to load modules for tests:")
        Logger.error(traceback.format_exc())

    registry = get_registry()
    if not registry:
        Logger.error("No tests registered. Use `core.unittest.case` to register tests.")
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
        Logger.info(f"TEST{i}: {fn.__name__}  ({entry.get("file")}:{entry.get("line")})")
        results = await _run_entry(entry)

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
                except KeyboardInterrupt:
                    print("")
                    Logger.warning("Interrupted by user.")
                    os._exit(1)
            elif expected is None:
                if r.get("output") is None:
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
