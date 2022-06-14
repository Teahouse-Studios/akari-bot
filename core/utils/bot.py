import asyncio
import logging
import os
import traceback

import ujson as json

from core.elements import PrivateAssets, StartUp, Schedule, Secret
from core.loader import load_modules, ModulesManager
from core.scheduler import Scheduler
from core.exceptions import ConfigFileNotFound
from core.logger import Logger
from core.utils.http import get_url

from configparser import ConfigParser
from os.path import abspath


bot_version = 'v4.0.0'


def init() -> None:
    """初始化机器人。仅用于bot.py与console.py。"""
    load_modules()
    version = os.path.abspath(PrivateAssets.path + '/version')
    write_version = open(version, 'w')
    try:
        write_version.write(os.popen('git rev-parse HEAD', 'r').read()[0:6])
    except Exception as e:
        write_version.write(bot_version)
    write_version.close()
    tag = os.path.abspath(PrivateAssets.path + '/version_tag')
    write_tag = open(tag, 'w')
    try:
        write_tag.write(os.popen('git tag -l', 'r').read().split('\n')[-2])
    except Exception as e:
        write_tag.write(bot_version)
    write_tag.close()


async def init_async(ft) -> None:
    gather_list = []
    Modules = ModulesManager.return_modules_list_as_dict()
    for x in Modules:
        if isinstance(Modules[x], StartUp):
            gather_list.append(asyncio.ensure_future(Modules[x].function(ft)))
        elif isinstance(Modules[x], Schedule):
            Scheduler.add_job(func=Modules[x].function, trigger=Modules[x].trigger, args=[ft], misfire_grace_time=30, max_instance=1)
    await asyncio.gather(*gather_list)
    Scheduler.start()
    logging.getLogger('apscheduler.executors.default').setLevel(logging.WARNING)
    await load_secret()


async def load_secret():
    config_filename = 'config.cfg'
    config_path = abspath('./config/' + config_filename)
    cp = ConfigParser()
    cp.read(config_path)
    section = cp.sections()
    if len(section) == 0:
        raise ConfigFileNotFound(config_path) from None
    section = section[0]
    options = cp.options(section)
    for option in options:
        value = cp.get(section, option)
        if value.upper() not in ['', 'TRUE', 'FALSE']:
            Secret.add(value.upper())
    try:
        ip = await get_url('https://api.ip.sb/ip')
        if ip:
            Secret.add(ip.replace('\n', ''))
    except Exception:
        Logger.error(traceback.format_exc())
        pass


async def load_prompt(bot) -> None:
    author_cache = os.path.abspath(PrivateAssets.path + '/cache_restart_author')
    loader_cache = os.path.abspath(PrivateAssets.path + '/.cache_loader')
    if os.path.exists(author_cache):
        open_author_cache = open(author_cache, 'r')
        author = json.loads(open_author_cache.read())['ID']
        open_loader_cache = open(loader_cache, 'r')
        m = await bot.fetch_target(author)
        if m:
            await m.sendDirectMessage(open_loader_cache.read())
            open_loader_cache.close()
            open_author_cache.close()
            os.remove(author_cache)
            os.remove(loader_cache)


__all__ = ['init', 'init_async', 'load_prompt']
