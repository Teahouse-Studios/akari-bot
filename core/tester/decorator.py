import inspect
from types import FunctionType
from typing import Callable, TypedDict

from .expectations import Expectation


class CaseEntry(TypedDict):
    """由 :func:`case` 注册的测试项。"""

    func: FunctionType
    input: str | list[str] | tuple[str, ...]
    expected: Expectation | None
    note: str | None
    timeout: float | None
    file: str | None
    line: int


_REGISTRY: list[CaseEntry] = []


def case(
    input_: str | list[str] | tuple[str, ...],
    expected: Expectation | None = None,
    note: str | None = None,
    timeout: float | None = None,
):
    """快捷注册一个测试案例。"""

    def _decorator(fn: FunctionType):
        entry: CaseEntry = {
            "func": fn,
            "input": input_,
            "expected": expected,
            "note": note,
            "timeout": timeout,
            "file": inspect.getsourcefile(fn),
            "line": inspect.getsourcelines(fn)[1],
        }
        _REGISTRY.append(entry)

        setattr(fn, "_casetest_meta", entry)

        return fn

    return _decorator


def get_registry() -> list[CaseEntry]:
    return list(_REGISTRY)


def func_case(fn: Callable):
    """标记函数是否为测试函数（测试时会被调用）。"""
    setattr(fn, "_func_case", True)
    return fn


__all__ = ["case", "func_case", "get_registry", "CaseEntry"]
