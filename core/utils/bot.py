import os
import re
import shutil
import traceback
import uuid
from os.path import abspath

import aiohttp
import filetype as ft

from core.logger import Logger

class PrivateAssets:
    path = ''

    @staticmethod
    def set(path):
        if not os.path.exists(path):
            os.mkdir(path)
        PrivateAssets.path = path


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

"""
async def load_prompt():
    author_cache = os.path.abspath('.cache_restart_author')
    loader_cache = os.path.abspath('.cache_loader')
    if os.path.exists(author_cache):
        import json
        open_author_cache = open(author_cache, 'r')
        cache_json = json.loads(open_author_cache.read())
        open_loader_cache = open(loader_cache, 'r')
        await sendMessage(cache_json, open_loader_cache.read(), quote=False)
        open_loader_cache.close()
        open_author_cache.close()
        os.remove(author_cache)
        os.remove(loader_cache)
"""