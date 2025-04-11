import sys

from tortoise import Tortoise

from core.builtins import MessageTaskManager
from core.logger import Logger


async def cleanup_sessions():
    get_wait_list = MessageTaskManager.get()
    Logger.warning('Cleaning up sessions...')
    for x in get_wait_list:
        for y in get_wait_list[x]:
            for z in get_wait_list[x][y]:
                if get_wait_list[x][y][z]["active"]:
                    await z.send_message(z.locale.t("core.message.restart.prompt"))
    await Tortoise.close_connections()


async def restart():
    await cleanup_sessions()
    sys.exit(233)


