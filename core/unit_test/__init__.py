import inspect
from typing import Any, Callable, Dict, List, Optional, Union

from core.builtins.types import MessageElement

_REGISTRY: List[dict] = []


def case(
    input_: str,
    expected: Optional[Union[str, list, MessageElement]] = None,
    manual: bool = False,
    sender_info: Optional[Dict[str, Any]] = None,
    target_info: Optional[Dict[str, Any]] = None,
    note: Optional[str] = None
):
    """
    注册一个单元测试案例。

    示例：
    ```
    @case("~test say Hello", "Hello is Hello")
    @test.command("say <word>")
    async def _(msg: Bot.MessageSession, word: str):
        await msg.finish(f"{word} is {msg.parsed_msg["<word>"]}")
    ```
    :param input: 预期输入。
    :param expected: 预期输出。
    :param manual: 是否使用人工检查。
    :param session_info: 预先设置的用户数据。
    :param target_info: 预先设置的会话数据。
    :param note: 额外说明。
    """

    def _decorator(fn: Callable):
        entry = {
            "func": fn,
            "input": input_,
            "expected": expected,
            "manual": manual,
            "sender_info": sender_info,
            "target_info": target_info,
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
