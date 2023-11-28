import asyncio
import logging
import os

import ujson as json

from config import CFG
from core.background_tasks import init_background_task
from core.loader import load_modules, ModulesManager
from core.logger import Logger, bot_name
from core.queue import JobQueue
from core.scheduler import Scheduler
from core.types import PrivateAssets, Secret
from core.utils.info import Info


async def init_async(start_scheduler=True) -> None:
    load_modules()
    gather_list = []
    modules = ModulesManager.return_modules_list()
    for x in modules:
        if schedules := modules[x].schedule_list.set:
            for schedule in schedules:
                Scheduler.add_job(func=schedule.function, trigger=schedule.trigger, misfire_grace_time=30,
                                  max_instance=1)
    await asyncio.gather(*gather_list)
    init_background_task()
    if start_scheduler:
        if not Info.subprocess:
            from core.extra.scheduler import load_extra_schedulers
            load_extra_schedulers()
            await JobQueue.secret_append_ip()
        Scheduler.start()
    logging.getLogger('apscheduler.executors.default').setLevel(logging.WARNING)
    await load_secret()
    try:
        Info.version = os.popen('git rev-parse HEAD', 'r').read()
    except Exception as e:
        Logger.warn(f'Failed to get git commit hash, is it a git repository?')
    Logger.info(f'Hello, {bot_name}!')


async def load_secret():
    for x in CFG.value:
        if x == 'secret':
            for y in CFG().value[x]:
                if CFG().value[x][y] is not None:
                    Secret.add(str(CFG().value[x][y]).upper())


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
                await m.send_direct_message(m.parent.locale.t('error.loader.load.failed', err_msg=read))
            else:
                await m.send_direct_message(m.parent.locale.t('error.loader.load.success'))
            open_loader_cache.close()
            open_author_cache.close()
            os.remove(author_cache)
            os.remove(loader_cache)


__all__ = ['init_async', 'load_prompt']
