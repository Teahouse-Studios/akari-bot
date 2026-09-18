import shutil


from core.builtins.bot import Bot
from core.builtins.message.internal import I18NContext
from core.config.base import CoreConfig
from core.component import module
from core.constants.path import cache_path
from core.scheduler import CronTrigger

auto_purge_crontab = CoreConfig.auto_purge_crontab

purge = module("purge", required_superuser=True, base=True, doc=True)


@purge.command("{{I18N:core.help.purge}}")
async def _(msg: Bot.MessageSession):
    if cache_path.exists():
        if len(list(cache_path.iterdir())) > 0:
            shutil.rmtree(cache_path)
            cache_path.mkdir(parents=True, exist_ok=True)
            await msg.finish(I18NContext("core.message.purge.success"))
        else:
            await msg.finish(I18NContext("core.message.purge.empty"))
    else:
        cache_path.mkdir(parents=True, exist_ok=True)
        await msg.finish(I18NContext("core.message.purge.empty"))


@purge.schedule(CronTrigger.from_crontab(auto_purge_crontab))
async def _():
    if cache_path.exists():
        shutil.rmtree(cache_path)
    cache_path.mkdir(parents=True, exist_ok=True)
