import asyncio
import logging
import os
import traceback

import ujson as json

from config import CFG
from core.loader import load_modules, ModulesManager
from core.logger import Logger, bot_name
from core.scheduler import Scheduler
from core.background_tasks import init_background_task
from core.types import PrivateAssets, Secret
from core.utils.http import get_url
from core.utils.ip import IP


async def init_async() -> None:
    load_modules()
    gather_list = []
    Modules = ModulesManager.return_modules_list()
    for x in Modules:
        if schedules := Modules[x].schedule_list.set:
            for schedule in schedules:
                Scheduler.add_job(func=schedule.function, trigger=schedule.trigger, misfire_grace_time=30,
                                  max_instance=1)
    await asyncio.gather(*gather_list)
    init_background_task()
    Scheduler.start()
    logging.getLogger('apscheduler.executors.default').setLevel(logging.WARNING)
    await load_secret()
    Logger.info(f'Hello, {bot_name}!')


async def load_secret():
    for x in CFG.value:
        if x == 'secret':
            for y in CFG().value[x]:
                if CFG().value[x][y] is not None:
                    Secret.add(str(CFG().value[x][y]).upper())

    async def append_ip():
        try:
            Logger.info('Fetching IP information...')
            ip = await get_url('https://api.ip.sb/geoip', timeout=10, fmt='json')
            if ip:
                Secret.add(ip['ip'])
                IP.country = ip['country']
                IP.address = ip['ip']
            Logger.info('Successfully fetched IP information.')
        except Exception:
            Logger.info('Failed to get IP information.')
            Logger.error(traceback.format_exc())

    asyncio.create_task(append_ip())


async def load_prompt(bot) -> None:
    author_cache = os.path.abspath(PrivateAssets.path + '/cache_restart_author')
    loader_cache = os.path.abspath(PrivateAssets.path + '/.cache_loader')
    if os.path.exists(author_cache):
        open_author_cache = open(author_cache, 'r')
        author = json.loads(open_author_cache.read())['ID']
        open_loader_cache = open(loader_cache, 'r')
        m = await bot.fetch_target(author)
        if m:
            if (read := open_loader_cache.read()) != '':
                await m.sendDirectMessage(m.parent.locale.t('error.loader.load.failed', err_msg=read))
            else:
                await m.sendDirectMessage(m.parent.locale.t('error.loader.load.success'))
            open_loader_cache.close()
            open_author_cache.close()
            os.remove(author_cache)
            os.remove(loader_cache)


__all__ = ['init_async', 'load_prompt']
