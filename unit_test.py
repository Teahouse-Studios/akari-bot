from core.parser import parser
import asyncio

kwargs = {}
kwargs['TEST'] = True
kwargs['command'] = '~ping'
asyncio.run(parser(kwargs))
