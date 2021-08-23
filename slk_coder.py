import asyncio
import sys

from graiax import silkcoder

filepath = sys.argv[1]
filepath2 = filepath + '.silk'
asyncio.run(silkcoder.encode(filepath, filepath2, rate=240000))
