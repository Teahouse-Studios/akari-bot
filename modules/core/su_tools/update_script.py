import time
import traceback

from core.builtins.bot import Bot
from core.builtins.message.internal import I18NContext, Plain
from core.component import module
from core.logger import Logger
from core.server.terminate import restart
from modules.core.su_tools.restart import restart_time, wait_for_restart, write_restart_cache
from modules.core.su_tools.update import pull_repo, update_dependencies

upds = module(
    "update&restart",
    required_superuser=True,
    alias="u&r",
    base=True,
    doc=True,
    exclude_from=["Web"],
    load=Bot.Info.subprocess,
)


@upds.command(
    "[--force] {{I18N:core.help.update&restart}}",
    options_desc={"--force": "{I18N:core.help.update&restart.option.force}"},
)
async def _(msg: Bot.MessageSession, force: bool = False):
    if not Bot.Info.binary_mode:
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
        if Bot.Info.version and Bot.Info.version.startswith("git:"):
            try:
                pull_repo_result = await pull_repo(force)
                if pull_repo_result:
                    await msg.send_message(Plain(pull_repo_result, disable_joke=True))
            except Exception:
                Logger.critical("Failed to send pull result message, perhaps bug? Continue...")
                Logger.critical(traceback.format_exc())
        try:
            update_dependencies_result = await update_dependencies()
            await msg.send_message(Plain(update_dependencies_result, disable_joke=True))
        except Exception:
            Logger.critical("Failed to send update dependencies result message, perhaps bug? Continue...")
            Logger.critical(traceback.format_exc())
        await restart()
    else:
        await msg.finish(I18NContext("core.message.update.binary_mode"))
