from typing import Any, Awaitable, Callable, Optional

import ujson as json
from langchain.tools import StructuredTool

from core.types.message import MessageSession, MsgInfo, Session
from core.utils.i18n import Locale


def to_json_func(func: Callable):
    async def wrapper(*args, **kwargs):
        return json.dumps(await func(*args, **kwargs))

    return wrapper


def to_async_func(func: Callable):
    async def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return wrapper


def with_args(func: Callable, *args, **kwargs):
    async def wrapper(*a, **k):
        # if a is tuple with empty string
        if len(a) == 1 and not a[0]:
            return await func(*args, **kwargs, **k)
        return await func(*args, *a, **kwargs, **k)

    return wrapper


def parse_input(input: str):
    if isinstance(input, list):  # wat hell it is appeared in here
        vals = input
    else:
        vals = input.split(',')
    parsed = []
    for v in vals:
        parsed.append(v.strip().strip('"'.strip("'")))
    return parsed


class AkariTool(StructuredTool):
    def __init__(
            self,
            name: str,
            func: Callable,
            coroutine=Optional[Callable[..., Awaitable[str]]],
            args_schema: Any = None,
            description: str = None,
            return_direct: bool = False):
        super().__init__(name=name, args_schema=args_schema, description=description,
                         return_direct=return_direct, func=func, coroutine=coroutine)
        self.coroutine = func


fake_msg = MessageSession(MsgInfo('Ask|0', 'Ask|0', 'AkariBot', 'Ask', 'Ask', 'Ask', 0),
                          Session('~lol lol', 'Ask|0', 'Ask|0'))
locale_en = Locale('en_us')
fake_msg.locale = locale_en
