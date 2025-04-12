import asyncio
import sys
import signal

from tortoise import Tortoise

from core.builtins import MessageTaskManager, I18NContext
from core.logger import Logger


async def cleanup_sessions():
    get_wait_list = MessageTaskManager.get()
    Logger.warning("Cleaning up sessions...")
    for x in get_wait_list:
        for y in get_wait_list[x]:
            for z in get_wait_list[x][y]:
                if get_wait_list[x][y][z]["active"]:
                    await z.send_message(I18NContext("core.message.restart.prompt"))
    await Tortoise.close_connections()


def catch_sigterm(signal, frame):
    Logger.warning("Caught SIGTERM. Exiting...")
    asyncio.get_running_loop().run_until_complete(cleanup_sessions())


signal.signal(signal.SIGTERM, catch_sigterm)


async def restart():
    await cleanup_sessions()
    sys.exit(233)
