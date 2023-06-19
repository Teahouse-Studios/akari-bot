from typing import Callable

import ujson as json
from langchain.agents import Tool

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
        if len(a) == 1 and a[0] == '':
            return await func(*args, **kwargs, **k)
        return await func(*args, *a, **kwargs, **k)
    return wrapper


def parse_input(input: str):
    vals = input.split(',')
    parsed = []
    for v in vals:
        parsed.append(v.strip().strip('"'.strip("'")))
    return parsed


class AkariTool(Tool):
    def __init__(self, name: str, func: Callable, description: str = None):
        super().__init__(name, func, description)
        self.coroutine = func


fake_msg = MessageSession(MsgInfo('Ask|0', 'Ask|0', 'AkariBot', 'Ask', 'Ask', 'Ask', 0),
                          Session('~lol lol', 'Ask|0', 'Ask|0'))
locale_en = Locale('en_us')
fake_msg.locale = locale_en
