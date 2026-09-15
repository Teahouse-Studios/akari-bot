"""把自研测试框架的 ``@func_case`` 入口接入 pytest 的适配层。

pytest 在这里只负责收集与报告，用例依旧由 :func:`core.tester.process.run_function_entry`
执行，因此条目级隔离（重建数据库、重新加载模块、watchdog 超时）与 ``tester.py`` 完全一致。

三条设计约束：

* 判定语义逐条对齐 ``tester.py`` 的失败分支。子测试不匹配、抛异常、条目超时或「注册了
  子测试却没产生结果」都判为失败，避免适配层出现假绿。
* 所有框架调用共用同一个会话事件循环。数据库连接与 ``ExpiringTempDict`` 的锁都绑定事件
  循环，混用多个循环会在已关闭的循环上留下持锁的任务。
* 本模块是框架里唯一依赖 pytest 的文件，且只在 pytest 运行时被导入，不影响 ``tester.py``。
"""

import asyncio
from collections.abc import Awaitable, Callable
from types import FunctionType
from typing import Any

import pytest

from .expectations import Expectation
from .tester import Tester

FUNC_CASE_ATTR = "_func_case"

_session_loop: asyncio.AbstractEventLoop | None = None


def get_session_loop() -> asyncio.AbstractEventLoop:
    """返回会话唯一的事件循环，不存在时新建并设为当前循环。"""
    global _session_loop
    if _session_loop is None or _session_loop.is_closed():
        _session_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_session_loop)
    return _session_loop


def run_in_session_loop(awaitable: Awaitable[Any]) -> Any:
    """
    在会话事件循环中执行协程。

    只能在同步调用点使用：事件循环不可重入，在异步测试函数里调用会抛 RuntimeError。

    :param awaitable: 待执行的协程。
    :return: 协程的返回值。
    """
    return get_session_loop().run_until_complete(awaitable)


async def _cancel_pending_tasks() -> None:
    """尽力取消遗留的后台任务，避免关闭循环时刷出大量 Task was destroyed 警告。"""
    current = asyncio.current_task()
    pending = [task for task in asyncio.all_tasks() if task is not current]
    if not pending:
        return
    for task in pending:
        task.cancel()
    await asyncio.wait(pending, timeout=1.0)


def close_session_loop() -> None:
    """
    关闭会话事件循环。

    框架加载的模块会留下未完成的后台任务，因此收尾是有界的：取消等待最多 1 秒。
    """
    global _session_loop
    loop, _session_loop = _session_loop, None
    if loop is None or loop.is_closed():
        return
    try:
        loop.run_until_complete(_cancel_pending_tasks())
    except Exception:
        pass
    finally:
        asyncio.set_event_loop(None)
        loop.close()


def _label_of(sub_result: dict[str, Any], index: int) -> str:
    """取子测试的可读标签，优先使用 note。"""
    return sub_result.get("note") or str(sub_result.get("input") or f"第 {index} 个子测试")


def describe_subresult(sub_result: dict[str, Any], label: str) -> tuple[str, str] | None:
    """
    判定单条子测试结果。

    :param sub_result: ``Tester`` 记录的单条结果。
    :param label: 失败信息中的子测试标签。
    :return: (类别, 详情)，类别为 ``error`` 或 ``failure``；通过或无需自动判定时为 None。
    """
    if "timeout" in sub_result:
        return "failure", f"{label}: 子测试超时"
    if "traceback" in sub_result:
        exception = sub_result.get("exception_type", "Exception")
        message = sub_result.get("exception_message", "")
        return "error", f"{label}: {exception}: {message}\n{sub_result['traceback']}"
    if sub_result.get("match"):
        return None
    if sub_result.get("expected") is None:
        # 与 tester.py 一致：无期望值的集成用例在 CI 下只标记人工复核，不计失败。
        return None
    expected = sub_result.get("expected")
    if sub_result.get("type") == "unit":
        target = getattr(expected, "__name__", str(expected))
        return "failure", f"{label}: {target} 返回假值，期望为真值"
    action = sub_result.get("action") or []
    actual = "\n".join(action) if action else "[NO OUTPUT]"
    return "failure", f"{label}: 期望 {expected}，实际 {actual}"


def evaluate_result(fn_name: str, res: dict[str, Any]) -> tuple[str, str] | None:
    """
    复核一次条目级运行结果，判定语义与 tester.py 保持一致。

    :param fn_name: 条目函数名，仅用于提示。
    :param res: :func:`core.tester.process.run_function_entry` 的返回值。
    :return: (类别, 详情)，类别为 ``error``/``failure``/``skip``；全部通过时为 None。
    """
    if res.get("error"):
        return "error", str(res["error"])

    if res.get("timeout"):
        detail = (
            f"{fn_name}: 无进展超时（{res.get('timeout_limit')}s），已完成子测试 {res.get('completed_tests', 0)} 个"
        )
        if res.get("active_test"):
            detail += f"\n卡住的子测试：{res['active_test']}"
        if res.get("cleanup_pending"):
            detail += "\n取消收尾超过时限"
        return "failure", detail

    entries = res.get("entries") or []
    results = res.get("results") or []
    if not entries:
        return "skip", f"{fn_name}: 没有注册任何子测试"
    if len(results) < len(entries):
        return "failure", f"{fn_name}: 注册了 {len(entries)} 个子测试，只产生 {len(results)} 条结果"

    details: list[str] = []
    kinds: set[str] = set()
    for index, sub_result in enumerate(results, 1):
        problem = describe_subresult(sub_result, _label_of(sub_result, index))
        if problem is None:
            continue
        kind, detail = problem
        kinds.add(kind)
        details.append(detail)
        if kind == "failure" or sub_result.get("type") == "integration":
            # runner 对 unit 子测试异常继续收集后续结果，对集成用例与不匹配则立即停止。
            break
    if not details:
        return None
    return ("error" if "error" in kinds else "failure"), "\n".join(details)


def fail_if_needed(kind: str, detail: str) -> None:
    """
    把判定结果转交给 pytest。

    :param kind: :func:`evaluate_result` 给出的类别。
    :param detail: 失败或跳过详情。
    """
    if kind == "skip":
        pytest.skip(detail)
    pytest.fail(detail, pytrace=False)


class FuncCaseItem(pytest.Item):
    """一个 ``@func_case`` 入口在 pytest 中的节点，执行仍交给框架完成。"""

    def __init__(self, *, fn: FunctionType, **kwargs: Any):
        super().__init__(**kwargs)
        self.fn = fn

    def runtest(self) -> None:
        """执行条目并复核结果，失败详情由判定函数给出。"""
        from .process import run_function_entry

        res = run_in_session_loop(run_function_entry(self.fn, is_ci=True))
        verdict = evaluate_result(self.fn.__name__, res)
        if verdict is not None:
            fail_if_needed(*verdict)

    def reportinfo(self) -> tuple[Any, int, str]:
        """报告节点位置，日志里显示为 ``文件::入口名``。"""
        return self.path, 0, f"[func_case] {self.name}"


class PytestTester(Tester):
    """
    面向纯 pytest 风格用例的同步运行器。

    ``@func_case`` 入口由适配层收集并用框架执行；本类让不写 ``@func_case`` 的用例复用同一
    套基座与判定：调用 ``test``/``integrate`` 立即返回结果，不匹配当场抛给 pytest，而不是
    留到收尾再断言，避免漏断言造成的假绿。接口是同步的（异步操作在会话事件循环里完成），
    因此只能在同步测试函数中使用。
    """

    def test(self, func: Callable, note: str | None = None):  # type: ignore[override]
        """执行纯函数子测试，失败立即判定为用例失败。"""
        result = run_in_session_loop(super().test(func, note))
        label = note or getattr(func, "__name__", type(func).__name__)
        problem = describe_subresult(result, label)
        if problem is not None:
            fail_if_needed(*problem)
        return result

    def integrate(  # type: ignore[override]
        self,
        input_: str | list[str] | tuple[str, ...],
        expected: Expectation | None = None,
        note: str | None = None,
        timeout: float | None = None,
    ):
        """执行一条命令级子测试，失败立即判定为用例失败。"""
        result = run_in_session_loop(super().integrate(input_, expected=expected, note=note, timeout=timeout))
        problem = describe_subresult(result, _label_of(result, 1))
        if problem is not None:
            fail_if_needed(*problem)
        return result


def make_item(collector: pytest.Collector, name: str, obj: object) -> pytest.Item | None:
    """
    把 ``@func_case`` 标记的入口替换为框架节点。

    :param collector: pytest 当前的收集器。
    :param name: 模块属性名。
    :param obj: 模块属性值。
    :return: 框架节点；不属于 ``@func_case`` 时返回 None，交回 pytest 默认收集。
    """
    if not isinstance(collector, pytest.Module):
        return None
    if not isinstance(obj, FunctionType) or not getattr(obj, FUNC_CASE_ATTR, False):
        return None
    return FuncCaseItem.from_parent(collector, name=name, fn=obj)


__all__ = [
    "FUNC_CASE_ATTR",
    "FuncCaseItem",
    "PytestTester",
    "close_session_loop",
    "describe_subresult",
    "evaluate_result",
    "fail_if_needed",
    "get_session_loop",
    "make_item",
    "run_in_session_loop",
]
