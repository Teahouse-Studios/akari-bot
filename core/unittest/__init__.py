import inspect
from typing import Any, Callable, List, Optional, Union


_REGISTRY: List[dict] = []


def case(
    input: Union[str, List[str]],
    expected: Optional[Any] = None,
    *,
    note: Optional[str] = None,
):
    """
    注册一个单元测试案例。

    參數:
    - input: 预期输入（字符串或字符串列表）。
    - expected: 预期输出；可以是字符串或任意可比較形态；若为 None 表示人工判定。
    - note: 额外说明文字。

    用法示例:
    @case(input="~test say Hello", expected="Hello is Hello")
    async def _(msg: Bot.MessageSession):
        ...
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
