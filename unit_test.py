import asyncio
import traceback

from core.elements import Target
from core.parser import parser

while True:
    try:
        kwargs = {}
        kwargs['TEST'] = True
        kwargs[Target] = Target(id=114514, senderId=1919810, name='tshe', target_from='Group')
        kwargs['command'] = input('> ')
        if '~' not in kwargs['command']:
            kwargs['command'] = '~' + kwargs['command']
        asyncio.run(parser(kwargs))
    except KeyboardInterrupt:
        print('已退出。')
        break
    except Exception:
        traceback.print_exc()
