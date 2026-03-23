import asyncio
import time
import traceback
from typing import Any, Callable

from core.builtins.message.chain import MessageChain, match_kecode
from core.builtins.message.elements import PlainElement
from core.constants.exceptions import SessionFinished
from core.database.models import SenderInfo, TargetInfo
from core.tester.mock.session import MockMessageSession
from core.tester.mock.parser import parser
from core.tester.mock.database import init_db, close_db
from core.tester.mock.loader import load_modules
from core.tester.mock.random import Random
from core.logger import Logger
from core.utils.container import ExpiringTempDict
from .expectations import Expectation


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
    timeout = entry.get("timeout")
    result = await run_test_case(entry["input"], entry["expected"], entry["func"], is_ci, timeout=timeout)
    elapsed = time.perf_counter() - start
    if "exception" in result and isinstance(result["expected"], Expectation):
        match = await result["expected"].match(result)
        if match:
            del result["traceback"]
    try:
        result["time_cost"] = elapsed
    except Exception:
        pass
    return [result]


async def run_function_entry(fn: Callable, is_ci: bool = False) -> dict[str, Any]:
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


async def run_test_case(
    input_: str | list[str] | tuple[str, ...],
    expected: Expectation | None = None,
    casetest_target: Callable | None = None,
    is_ci: bool = False,
    timeout: float | None = None,
):
    async def _run_test():
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
        except SessionFinished:
            pass
        except Exception as e:
            err_msg = msg.session_info.locale.t_str(str(e))
            try:
                err_chain = match_kecode(err_msg, disable_joke=True)
            except Exception:
                err_chain = MessageChain.assign(err_msg)

            err_action = [
                x.text if isinstance(x, PlainElement) else str(x) for x in err_chain.as_sendable(msg.session_info)
            ]

            return {
                "input": input_,
                "exception": e,
                "exception_message": err_chain.to_str(),
                "action": [f"(raise {type(e).__name__})"] + err_action,
                "traceback": traceback.format_exc(),
                "expected": expected,
            }
        finally:
            await ExpiringTempDict.clear_all(now=time.time() + 31536000)

        return {
            "input": input_,
            "output": msg.sent,
            "action": msg.action,
            "expected": expected,
        }

    if timeout:
        try:
            result = await asyncio.wait_for(_run_test(), timeout=timeout)
        except asyncio.TimeoutError:
            await ExpiringTempDict.clear_all(now=time.time() + 31536000)
            result = {"input": input_, "expected": expected, "timeout": True}
    else:
        result = await _run_test()
    return result
