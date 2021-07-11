import os
import re

import aiohttp


async def load_prompt():
    author_cache = os.path.abspath('.cache_restart_author')
    loader_cache = os.path.abspath('.cache_loader')
    if os.path.exists(author_cache):
        import json
        from core.template import sendMessage
        open_author_cache = open(author_cache, 'r')
        cache_json = json.loads(open_author_cache.read())
        open_loader_cache = open(loader_cache, 'r')
        await sendMessage(cache_json, open_loader_cache.read(), Quote=False)
        open_loader_cache.close()
        open_author_cache.close()
        os.remove(author_cache)
        os.remove(loader_cache)


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


def replace_alias_to_correct_name():

