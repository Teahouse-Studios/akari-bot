import asyncio

from core.parser import parser

kwargs = {}
kwargs['TEST'] = True
kwargs['command'] = '~github search mcwzh'
asyncio.run(parser(kwargs))
