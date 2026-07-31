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
    """
    快捷注册一个测试案例。

    示例：
    ```
    from core.tester import case, Match

    @case("~test say Hello", Match("Hello is Hello"))
    @test.command("say <word>")
    async def _(msg: Bot.MessageSession, word: str):
        await msg.finish(f"{word} is {msg.parsed_msg["<word>"]}")
    ```
    :param input_: 预期输入。
    :param expected: 预期输出，传入期望匹配器，若为 None 则手动复核。
    :param note: 额外说明。
    :param timeout: 超时时间（秒），若为 None 则无超时限制。
    """

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
