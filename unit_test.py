from core.parser import parser
import asyncio

kwargs = {}
kwargs['TEST'] = True
kwargs['command'] = '~github user Dianliang233'
asyncio.run(parser(kwargs))
