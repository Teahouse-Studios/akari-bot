import sys

from tortoise import Tortoise


async def restart():
    await Tortoise.close_connections()
    sys.exit(233)


async def shutdown():
    await Tortoise.close_connections()
