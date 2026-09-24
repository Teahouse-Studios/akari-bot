import asyncio
import time
import traceback
from types import FunctionType
from typing import Any, Callable

from core.builtins.message.chain import MessageChain, match_kecode
from core.builtins.message.elements import PlainElement
from core.constants.exceptions import SessionFinished
from core.database.models import SenderUnionInfo, TargetUnionInfo
from core.logger import Logger
from core.tester.mock.database import close_db, get_last_init_error, init_db
from core.tester.mock.loader import load_modules
from core.tester.mock.parser import parser
from core.tester.mock.random import Random
from core.tester.mock.session import MockMessageSession
from core.utils.container import ExpiringTempDict
from .decorator import CaseEntry
from .expectations import Expectation
from .timing import TIME_SCALE

# 无进展看门狗随测试时限系数放大，但封顶 5 倍：慢机器上子测试可以更久，
# 真正卡死时也不能让单个用例占用整个 CI 任务太久。
DEFAULT_FUNCTION_TEST_TIMEOUT = 120.0 * min(TIME_SCALE, 5.0)
FUNCTION_TEST_CANCEL_TIMEOUT = 1.0 * TIME_SCALE


class _FunctionTestNoProgress(Exception):
    pass


def _consume_task_result(task: asyncio.Task) -> None:
    if task.cancelled():
        return
    try:
        task.exception()
    except asyncio.CancelledError:
        pass


async def _cancel_task(task: asyncio.Task) -> bool:
    if task.done():
        await asyncio.gather(task, return_exceptions=True)
        return True
    task.cancel()
    done, _ = await asyncio.wait((task,), timeout=FUNCTION_TEST_CANCEL_TIMEOUT)
    if task not in done:
        task.cancel()
        task.add_done_callback(_consume_task_result)
        return False
    await asyncio.gather(task, return_exceptions=True)
    return True


async def _cancel_orphan_tasks(baseline: set[asyncio.Task] | None = None) -> bool:
    current = asyncio.current_task()
    tasks = [
        task
        for task in asyncio.all_tasks()
        if task is not current
        and not task.done()
        and not task.get_name().startswith("function-test-progress:")
        and (baseline is None or task not in baseline)
    ]
    if not tasks:
        return True
    completed = await asyncio.gather(*(_cancel_task(task) for task in tasks))
    return all(completed)


def _infrastructure_error(input_, expected, message: str) -> list[dict]:
    return [{"input": input_, "expected": expected, "traceback": message, "action": []}]


async def run_case_entry(entry: CaseEntry, is_ci: bool = False) -> list[dict]:
    baseline_tasks = set(asyncio.all_tasks())

    try:
        await close_db()
    except Exception:
        Logger.exception("Error closing database before test")

    if not await init_db():
        message = f"Failed to reinitialize database for case {entry.get('func')}.\n{get_last_init_error()}"
        Logger.critical(message)
        return _infrastructure_error(entry.get("input"), entry.get("expected"), message)

    try:
        try:
            await load_modules(show_logs=False, monkey_patches={"Random": Random()})
        except Exception:
            error = traceback.format_exc()
            Logger.exception("Failed to load modules for tests:")
            return _infrastructure_error(entry.get("input"), entry.get("expected"), error)

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
    finally:
        # Integration cases can start queue pollers, waiters, or platform tasks.
        # They share the event loop and in-memory database with later cases, so a
        # detached task must not survive the database context it captured.
        if not await _cancel_orphan_tasks(baseline_tasks):
            message = "Registry test left a task that did not finish cancellation cleanup."
            Logger.error(message)
            raise RuntimeError(message)


async def run_function_entry(
    fn: FunctionType, is_ci: bool = False, timeout: float | None = DEFAULT_FUNCTION_TEST_TIMEOUT
) -> dict[str, Any]:
    # Every func_case is an isolation boundary. Record existing runner tasks so
    # only work started by this entry is reclaimed after it finishes.
    cleanup_pending = False
    baseline_tasks = set(asyncio.all_tasks())
    try:
        await close_db()
    except Exception:
        Logger.exception("Error closing database before func test")

    if not await init_db():
        message = f"Failed to reinitialize database for func test {fn.__name__}.\n{get_last_init_error()}"
        Logger.critical(message)
        return {"error": message}

    try:
        await load_modules(show_logs=False, monkey_patches={"Random": Random()})
    except Exception:
        error = traceback.format_exc()
        Logger.exception("Failed to load modules for tests:")
        return {"error": error}

    tester = None
    start = time.perf_counter()
    try:
        from core.tester import Tester as TesterClass

        tester = TesterClass(fn.__name__)
        setattr(tester, "is_ci", is_ci)
        if timeout is None:
            returned = await fn(tester)
        else:
            function_task = asyncio.create_task(fn(tester))
            progress_task = None
            progress_revision = tester._progress_revision
            progress_deadline = asyncio.get_running_loop().time() + timeout
            try:
                while True:
                    progress_task = asyncio.create_task(
                        tester._wait_for_progress(progress_revision),
                        name=f"function-test-progress:{fn.__name__}",
                    )
                    remaining = max(0.0, progress_deadline - asyncio.get_running_loop().time())
                    done, _ = await asyncio.wait(
                        (function_task, progress_task),
                        timeout=remaining,
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    if function_task in done:
                        progress_task.cancel()
                        await asyncio.gather(progress_task, return_exceptions=True)
                        returned = function_task.result()
                        break
                    if progress_task in done:
                        current_revision = tester._progress_revision
                        if not progress_task.cancelled():
                            current_revision = progress_task.result()
                        if current_revision > progress_revision:
                            progress_revision = current_revision
                            progress_deadline = asyncio.get_running_loop().time() + timeout
                        elif asyncio.get_running_loop().time() >= progress_deadline:
                            raise _FunctionTestNoProgress
                        continue
                    raise _FunctionTestNoProgress
            finally:
                if progress_task is not None and not progress_task.done():
                    await _cancel_task(progress_task)
                if not function_task.done():
                    cleanup_pending = not await _cancel_task(function_task)
        if isinstance(returned, TesterClass):
            tester = returned
    except _FunctionTestNoProgress:
        elapsed = time.perf_counter() - start
        entries = tester.get_entries() if tester is not None else []
        results = tester.get_results() if tester is not None else []
        active_test = None
        if len(entries) > len(results):
            active_entry = entries[len(results)]
            active_test = active_entry.get("note") or active_entry.get("input")
            if active_test is None:
                expected = active_entry.get("expected")
                active_test = getattr(expected, "__name__", type(expected).__name__)
        message = f"Function test {fn.__name__} made no progress for {timeout} seconds"
        if active_test:
            message += f" while running {active_test!r}"
        Logger.error(f"{message}.")
        cleanup_pending = not await _cancel_orphan_tasks(baseline_tasks) or cleanup_pending
        return {
            "timeout": True,
            "time_cost": elapsed,
            "timeout_limit": timeout,
            "active_test": active_test,
            "completed_tests": len(results),
            "cleanup_pending": cleanup_pending,
            "entries": entries,
            "results": results,
        }
    except (asyncio.CancelledError, KeyboardInterrupt, SystemExit, GeneratorExit):
        raise
    except BaseException:
        error = traceback.format_exc()
        Logger.exception(f"Error running test function {fn.__name__}:")
        cleanup_pending = not await _cancel_orphan_tasks(baseline_tasks) or cleanup_pending
        return {"error": error, "cleanup_pending": cleanup_pending}

    cleanup_pending = not await _cancel_orphan_tasks(baseline_tasks) or cleanup_pending

    elapsed = time.perf_counter() - start
    entries = tester.get_entries()
    results = tester.get_results()
    return {
        "tester": tester,
        "entries": entries,
        "results": results,
        "time_cost": elapsed,
        "cleanup_pending": cleanup_pending,
    }


async def run_test_case(
    input_: str | list[str] | tuple[str, ...],
    expected: Expectation | None = None,
    casetest_target: Callable | None = None,
    is_ci: bool = False,
    timeout: float | None = None,
):
    async def _run_test():
        try:
            await TargetUnionInfo.resolve_union("TEST|Console|0")
            sender_union_info = await SenderUnionInfo.resolve_union("TEST|0")
            await sender_union_info.edit_attr("superuser", True)
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
