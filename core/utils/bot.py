'''编写机器人时可能会用到的一些工具类方法。'''
import os
import traceback
import uuid
from os.path import abspath
from typing import Union

import aiohttp
import filetype as ft
import ujson as json
from aiohttp_retry import ExponentialRetry, RetryClient

from core.elements import FetchTarget
from core.logger import Logger


class PrivateAssets:
    path = os.path.abspath('.')

    @staticmethod
    def set(path: str) -> None:
        '''创建一个文件夹以储存资源。请配合.gitignore使用。'''
        path = os.path.abspath(path)
        if not os.path.exists(path):
            os.mkdir(path)
        PrivateAssets.path = path


def init() -> None:
    '''初始化机器人。仅用于bot.py与unit_test.py。'''
    version = os.path.abspath(PrivateAssets.path + '/version')
    write_version = open(version, 'w')
    write_version.write(os.popen('git rev-parse HEAD', 'r').read()[0:6])
    write_version.close()
    tag = os.path.abspath(PrivateAssets.path + '/version_tag')
    write_tag = open(tag, 'w')
    write_tag.write(os.popen('git tag -l', 'r').read().split('\n')[-2])
    write_tag.close()


async def get_url(url: str, headers: list=None) -> str:
    '''利用AioHttp获取指定url的内容。
    
    :param url: 需要获取的url。
    :param headers: 请求时使用的http头。
    :returns: 指定url的内容（字符串）。'''
    async with RetryClient(headers=headers, retry_options=ExponentialRetry(attempts=3)) as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=20), headers=headers) as req:
            text = await req.text()
            return text


async def download_to_cache(link: str) -> Union[str, False]:
    '''利用AioHttp下载指定url的内容，并保存到缓存（./cache目录）。
    
    :param link: 需要获取的link。
    :returns: 文件的相对路径，若获取失败则返回False。'''
    try:
        async with RetryClient(retry_options=ExponentialRetry(attempts=3)) as session:
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


async def slk_converter(filepath: str) -> str:
    '''将指定文件转为slk格式。
    
    :param filepath: 需要获取的link。
    :returns: 文件的相对路径。'''
    filepath2 = filepath + '.silk'
    Logger.info('Start encoding voice...')
    os.system('python slk_coder.py ' + filepath)
    Logger.info('Voice encoded.')
    return filepath2


async def load_prompt(bot: FetchTarget) -> None:
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
