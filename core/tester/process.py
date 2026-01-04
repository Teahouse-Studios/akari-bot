import time
import traceback
from typing import Any

from core.builtins.message.chain import MessageChain, match_kecode
from core.builtins.message.elements import PlainElement
from core.builtins.session.info import SessionInfo
from core.builtins.types import MessageElement
from core.constants.exceptions import (
    AbuseWarning,
    FinishedException,
    NoReportException,
    TestException,
)
from core.cooldown import _cd_dict
from core.database.models import SenderInfo, TargetInfo
from core.game import _ps_dict
from core.tester.mock.session import MockMessageSession
from core.tester.mock.parser import parser
from core.tester.mock.database import init_db, close_db
from core.tester.mock.loader import load_modules
from core.tester.mock.random import Random
from core.logger import Logger


async def run_case_entry(entry: dict, is_ci: bool = False) -> list[dict]:
    try:
        await close_db()
    except Exception:
        Logger.exception("Error closing database before test")

    if not await init_db():
        Logger.critical(f"Failed to reinitialize database for case {entry.get('func')}. Skipping tests.")
        return []

    try:
        await load_modules(show_logs=False, monkey_patches={"Random": Random()})
    except Exception:
        Logger.exception("Failed to load modules for tests:")

    start = time.perf_counter()
    result = await run_single_test(entry["input"], casetest_target=entry.get("func"), is_ci=is_ci)
    elapsed = time.perf_counter() - start
    try:
        result["time_cost"] = elapsed
    except Exception:
        pass
    return [result]


async def run_function_test(fn, is_ci: bool = False) -> dict[str, Any]:
    try:
        await close_db()
    except Exception:
        Logger.exception("Error closing database before func test")

    if not await init_db():
        Logger.critical(f"Failed to reinitialize database for func test {fn.__name__}. Skipping.")
        return {"skipped": True}

    try:
        await load_modules(show_logs=False, monkey_patches={"Random": Random()})
    except Exception:
        Logger.exception("Failed to load modules for tests:")

    tester = None
    start = time.perf_counter()
    try:
        from core.tester import Tester as TesterClass

        tester = TesterClass(fn.__name__)
        setattr(tester, "is_ci", is_ci)
        returned = await fn(tester)
        if isinstance(returned, TesterClass):
            tester = returned
    except Exception:
        Logger.exception(f"Error running test function {fn.__name__}:")
        return {"error": True}

    elapsed = time.perf_counter() - start
    entries = tester.get_entries()
    results = tester.get_results()
    return {"tester": tester, "entries": entries, "results": results, "time_cost": elapsed}


async def run_single_test(
    input_: str | list[str] | tuple[str, ...],
    *,
    casetest_target=None,
    is_ci=False
):
    try:
        await TargetInfo.update_or_create(defaults={}, target_id="TEST|Console|0")
        await SenderInfo.update_or_create(defaults={"superuser": True}, sender_id="TEST|0")
    except Exception:
        pass

    msg = MockMessageSession(input_, is_ci=is_ci)
    await msg.async_init(msg.trigger_msg)

    if casetest_target is not None:
        setattr(msg, "_casetest_target", casetest_target)

    try:
        await parser(msg)
    except FinishedException:
        pass
    except (AbuseWarning, NoReportException, TestException) as e:
        err_msg = msg.session_info.locale.t_str(str(e))
        try:
            err_chain = match_kecode(err_msg, disable_joke=True)
        except Exception:
            err_chain = MessageChain(err_msg)

        err_action = [
            x.text if isinstance(x, PlainElement) else str(x)
            for x in err_chain.as_sendable(msg.session_info)
        ]

        return {
            "input": input_,
            "output": err_chain,
            "action": [f"(raise {type(e).__name__})"] + err_action,
            "exception": type(e).__name__,
        }
    except Exception:
        return {
            "input": input_,
            "error": traceback.format_exc(),
        }
    finally:
        _cd_dict.clear()
        _ps_dict.clear()

    return {
        "input": input_,
        "output": msg.sent,
        "action": msg.action,
    }


async def match_expected(
    output,
    expected: bool | str | MessageChain | list[MessageElement] | tuple[MessageElement, ...] | MessageElement,
) -> bool | None:
    if expected is None:  # noqa
        return None
    if expected is True:  # noqa
        return bool(output)
    if expected is False:  # noqa
        return not bool(output)

    session_info = await SessionInfo.assign(
        target_id="TEST|Console|0",
        client_name="TEST",
        target_from="TEST",
        sender_id="TEST|0",
        sender_from="TEST",
    )

    expected_chain = MessageChain.assign(expected).as_sendable(session_info)
    return output == expected_chain
