import asyncio
import traceback

from core.parser import parser

while True:
    try:
        kwargs = {}
        kwargs['TEST'] = True
        kwargs['command'] = input('> ')
        if '~' not in kwargs['command']:
            kwargs['command'] = '~' + kwargs['command']
        asyncio.run(parser(kwargs))
    except KeyboardInterrupt:
        print('已退出。')
        break
    except Exception:
        traceback.print_exc()
