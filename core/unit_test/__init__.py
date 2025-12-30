import inspect
from typing import Callable, List, Optional, Union

from core.builtins.types import MessageElement

_REGISTRY: List[dict] = []


def case(
    input: str,
    expected: Optional[Union[str, list, MessageElement]] = None,
    manual: bool = False,
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
    :param expected: 预期输出。
    :param manual: 是否采用人工检查。
    :param note: 额外说明文字。
    """

    def _decorator(fn: Callable):
        entry = {
            "func": fn,
            "input": input,
            "expected": expected,
            "manual": manual,
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
