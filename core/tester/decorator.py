import inspect
from typing import Callable

from core.builtins.message.chain import MessageChain
from core.builtins.types import MessageElement
from core.tester.process import run_case_entry


_REGISTRY: list[dict] = []


def case(input_: str | list[str] | tuple[str, ...],
         expected: bool |
         str |
         MessageChain |
         list[MessageElement] |
         tuple[MessageElement, ...] |
         MessageElement |
         None = None,
         note: str | None = None):
    """
    快捷注册一个测试案例。

    示例：
    ```
    @case("~test say Hello", "Hello is Hello")
    @test.command("say <word>")
    async def _(msg: Bot.MessageSession, word: str):
        await msg.finish(f"{word} is {msg.parsed_msg["<word>"]}")
    ```
    :param input: 预期输入。
    :param expected: 预期输出，若为 bool 则表示是否存在输出，否则将对比预期输出。
    :param note: 额外说明。
    """

    def _decorator(fn: Callable):
        entry = {
            "func": fn,
            "input": input_,
            "expected": expected,
            "note": note,
            "file": inspect.getsourcefile(fn),
            "line": inspect.getsourcelines(fn)[1],
        }
        _REGISTRY.append(entry)

        setattr(fn, "_casetest_meta", entry)

        return fn

    return _decorator


def get_registry():
    return list(_REGISTRY)


async def run_registry(entry: dict, is_ci: bool = False):
    return await run_case_entry(entry, is_ci)


def func_case(fn: Callable):
    """标记函数是否为测试函数（测试时会被调用）。"""
    setattr(fn, "_func_case", True)
    return fn


__all__ = ["case", "func_case", "get_registry", "run_registry"]
