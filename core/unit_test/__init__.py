import inspect
from typing import Callable, List, Optional

from core.builtins.message.chain import Chainable

_REGISTRY: List[dict] = []


def case(
    input: str,
    expected: Optional[Chainable] = None,
    note: Optional[str] = None
):
    """
    注册一个单元测试案例。

    示例：
    ```
    @case(input="~test say Hello", expected="Hello is Hello")
    @test.command("say <word>")
    async def _(msg: Bot.MessageSession, word: str):
        await msg.finish(f"{word} is {msg.parsed_msg["<word>"]}")
    ```
    :param input: 预期输入。
    :param expected: 预期输出，若为 None 则表示人工判断。
    :param note: 额外说明文字。
    """

    def _decorator(fn: Callable):
        entry = {
            "func": fn,
            "input": input,
            "expected": expected,
            "note": note,
            "file": inspect.getsourcefile(fn),
            "line": inspect.getsourcelines(fn)[1],
        }
        _REGISTRY.append(entry)

        setattr(fn, "_unittest_meta", entry)

        return fn

    return _decorator


def get_registry():
    return list(_REGISTRY)


__all__ = ["case", "get_registry"]
