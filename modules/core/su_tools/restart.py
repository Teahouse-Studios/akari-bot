import time
import traceback

import orjson

from core.builtins.bot import Bot
from core.builtins.converter import converter
from core.builtins.message.internal import I18NContext
from core.component import module
from core.logger import Logger
from core.server.terminate import restart

rst = module("restart", required_superuser=True, base=True, doc=True, exclude_from=["Web"], load=Bot.Info.subprocess)


def write_restart_cache(msg: Bot.MessageSession):
    update = Bot.PrivateData.path / ".cache_restart_author"
    with open(update, "wb") as write_version:
        write_version.write(orjson.dumps(converter.unstructure(msg.session_info)))


restart_time = []


async def wait_for_restart(msg: Bot.MessageSession):
    active_commands = Bot.ExecutionLockList.count(exclude=msg)
    if time.time() - restart_time[0] < 60:
        if active_commands:
            await msg.send_message(I18NContext("core.message.restart.wait", count=active_commands))
            await msg.sleep(10)
            return await wait_for_restart(msg)
        await msg.send_message(I18NContext("core.message.restart.restarting"))
    else:
        await msg.send_message(I18NContext("core.message.restart.timeout"))


@rst.command("[--force] {{I18N:core.help.restart}}", options_desc={"--force": "{I18N:core.help.restart.force}"})
async def _(msg: Bot.MessageSession, force: bool = False):
    if force:
        await msg.send_message(I18NContext("core.message.restart.restarting"))
    else:
        try:
            if not await msg.wait_confirm(append_instruction=False):
                await msg.finish()
            else:
                if not restart_time:
                    restart_time.append(time.time())
                await wait_for_restart(msg)
        except Exception:
            Logger.critical("Failed to send restart confirmation message, perhaps bug? Force restart...")
            Logger.critical(traceback.format_exc())
    try:
        restart_time.append(time.time())
        write_restart_cache(msg)
    except Exception:
        Logger.critical("Failed to write restart info cache, perhaps bug? Continue...")
        Logger.critical(traceback.format_exc())
    await restart()
