import os
import re
import traceback
import uuid
from os.path import abspath

import aiohttp
import filetype as ft

from core.logger import Logger

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


async def get_url(url: str, headers=None):
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=20), headers=headers) as req:
            text = await req.text()
            return text


def remove_ineffective_text(prefix, lst):
    remove_list = ['\n', ' ']  # 首尾需要移除的东西
    for x in remove_list:
        list_cache = []
        for y in lst:
            split_list = y.split(x)
            for _ in split_list:
                if split_list[0] == '':
                    del split_list[0]
                if len(split_list) > 0:
                    if split_list[-1] == '':
                        del split_list[-1]
            for _ in split_list:
                if len(split_list) > 0:
                    if split_list[0][0] in prefix:
                        split_list[0] = re.sub(r'^' + split_list[0][0], '', split_list[0])
            list_cache.append(x.join(split_list))
        lst = list_cache
    duplicated_list = []  # 移除重复命令
    for x in lst:
        if x not in duplicated_list:
            duplicated_list.append(x)
    lst = duplicated_list
    return lst


def RemoveDuplicateSpace(text: str):
    strip_display_space = text.split(' ')
    display_list = []  # 清除指令中间多余的空格
    for x in strip_display_space:
        if x != '':
            display_list.append(x)
    text = ' '.join(display_list)
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
