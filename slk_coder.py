from graiax import silkcoder
import asyncio
import sys

filepath = sys.argv[1]
filepath2 = filepath + '.silk'
asyncio.run(silkcoder.encode(filepath, filepath2, rate=240000))
