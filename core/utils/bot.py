import json
import os
import traceback
import uuid
from os.path import abspath

import aiohttp
import filetype as ft

from core.elements import FetchTarget
from core.logger import Logger


class PrivateAssets:
    path = ''

    @staticmethod
    def set(path):
        if not os.path.exists(path):
            os.mkdir(path)
        PrivateAssets.path = path


def init():
    version = os.path.abspath(PrivateAssets.path + '/version')
    write_version = open(version, 'w')
    write_version.write(os.popen('git rev-parse HEAD', 'r').read()[0:7])
    write_version.close()
    tag = os.path.abspath(PrivateAssets.path + '/version_tag')
    write_tag = open(tag, 'w')
    write_tag.write(os.popen('git tag -l', 'r').read().split('\n')[-2])
    write_tag.close()


async def get_url(url: str, headers=None):
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=20), headers=headers) as req:
            text = await req.text()
            return text


async def download_to_cache(link):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(link) as resp:
                res = await resp.read()
                ftt = ft.match(res).extension
                path = abspath(f'./cache/{str(uuid.uuid4())}.{ftt}')
                with open(path, 'wb+') as file:
                    file.write(res)
                    return path
    except:
        traceback.print_exc()
        return False


def cache_name():
    return abspath(f'./cache/{str(uuid.uuid4())}')


async def slk_converter(filepath):
    filepath2 = filepath + '.silk'
    Logger.info('Start encoding voice...')
    os.system('python slk_coder.py ' + filepath)
    Logger.info('Voice encoded.')
    return filepath2


async def load_prompt(bot: FetchTarget):
    author_cache = os.path.abspath(PrivateAssets.path + '/cache_restart_author')
    loader_cache = os.path.abspath('.cache_loader')
    if os.path.exists(author_cache):
        open_author_cache = open(author_cache, 'r')
        author = json.loads(open_author_cache.read())['ID']
        open_loader_cache = open(loader_cache, 'r')
        m = await bot.fetch_target(author)
        if m:
            await m.sendMessage(open_loader_cache.read())
            open_loader_cache.close()
            open_author_cache.close()
            os.remove(author_cache)
            os.remove(loader_cache)
