import asyncio

from core.parser import parser

kwargs = {}
kwargs['TEST'] = True
kwargs['command'] = '~github user Dianliang233'
asyncio.run(parser(kwargs))
