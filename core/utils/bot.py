'''编写机器人时可能会用到的一些工具类方法。'''
import os
import traceback
import uuid
from os.path import abspath
from typing import Union

import aiohttp
import filetype as ft
import ujson as json
from tenacity import retry, wait_fixed, stop_after_attempt

from core.elements import PrivateAssets
from core.loader import load_modules
from core.logger import Logger


def init() -> None:
    '''初始化机器人。仅用于bot.py与console.py。'''
    load_modules()
    version = os.path.abspath(PrivateAssets.path + '/version')
    write_version = open(version, 'w')
    try:
        write_version.write(os.popen('git rev-parse HEAD', 'r').read()[0:6])
    except ValueError:
        write_version.write('Not a git repo')
    write_version.close()
    tag = os.path.abspath(PrivateAssets.path + '/version_tag')
    write_tag = open(tag, 'w')
    try:
        write_tag.write(os.popen('git tag -l', 'r').read().split('\n')[-2])
    except ValueError:
        write_tag.write('v4.?.?')
    write_tag.close()


@retry(stop=stop_after_attempt(3), wait=wait_fixed(3), reraise=True)
async def get_url(url: str, status_code: int = False, headers: dict = None, fmt=None, log=False):
    """利用AioHttp获取指定url的内容。

    :param url: 需要获取的url。
    :param status_code: 指定请求到的状态码，若不符则抛出ValueError。
    :param headers: 请求时使用的http头。
    :param fmt: 指定返回的格式。
    :param log: 是否输出日志。
    :returns: 指定url的内容（字符串）。
    """
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=20), headers=headers) as req:
            if log:
                Logger.info(await req.read())
            if status_code and req.status != status_code:
                raise ValueError(f'{str(req.status)}[Ke:Image,path=https://http.cat/{str(req.status)}.jpg]')
            if fmt is not None:
                if hasattr(req, fmt):
                    return await getattr(req, fmt)()
                else:
                    raise ValueError(f"NoSuchMethod: {fmt}")
            else:
                text = await req.text()
                return text


@retry(stop=stop_after_attempt(3), wait=wait_fixed(3), reraise=True)
async def post_url(url: str, data: any, headers: dict = None):
    '''发送POST请求。
    :param url: 需要发送的url。
    :param data: 需要发送的数据。
    :param headers: 请求时使用的http头。
    :returns: 发送请求后的响应。'''
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.post(url, data=data, headers=headers) as req:
            return await req.text()


@retry(stop=stop_after_attempt(3), wait=wait_fixed(3), reraise=True)
async def download_to_cache(link: str) -> Union[str, bool]:
    '''利用AioHttp下载指定url的内容，并保存到缓存（./cache目录）。

    :param link: 需要获取的link。
    :returns: 文件的相对路径，若获取失败则返回False。'''
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
        Logger.error(traceback.format_exc())
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
