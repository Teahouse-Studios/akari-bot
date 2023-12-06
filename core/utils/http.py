import asyncio.exceptions
import re
import socket
import urllib.parse
from typing import Union

import aiohttp
import filetype as ft
from aiofile import async_open
from aiohttp import TCPConnector
from tenacity import retry, wait_fixed, stop_after_attempt

from config import Config
from core.logger import Logger
from .cache import random_cache_path

logging_resp = False
debug = Config('debug')
if not (proxy := Config('proxy')):
    proxy = ''

_matcher_private_ips = re.compile(
    r'^(?:127\.|0?10\.|172\.0?1[6-9]\.|172\.0?2[0-9]\.172\.0?3[01]\.|192\.168\.|169\.254\.|::1|[fF][cCdD][0-9a-fA-F]{2}:|[fF][eE][89aAbB][0-9a-fA-F]:)'
)


def private_ip_check(url: str):
    '''检查是否为私有IP，若是则抛出ValueError异常。

    :param url: 需要检查的url。'''
    hostname = urllib.parse.urlparse(url).hostname
    addr_info = socket.getaddrinfo(hostname, 80)

    addr = addr_info[0][4][0]
    if _matcher_private_ips.match(addr):
        raise ValueError(
            f'Attempt of requesting private IP addresses is not allowed, requesting {hostname}.')


async def get_url(url: str, status_code: int = False, headers: dict = None, params: dict = None, fmt=None, timeout=20,
                  attempt=3,
                  request_private_ip=False, logging_err_resp=True):
    """利用AioHttp获取指定url的内容。

    :param url: 需要获取的url。
    :param status_code: 指定请求到的状态码，若不符则抛出ValueError。
    :param headers: 请求时使用的http头。
    :param params: 请求时使用的参数。
    :param fmt: 指定返回的格式。
    :param timeout: 超时时间。
    :param attempt: 指定请求尝试次数。
    :param request_private_ip: 是否允许请求私有IP。
    :param logging_err_resp: 是否记录错误响应。
    :returns: 指定url的内容（字符串）。
    """

    @retry(stop=stop_after_attempt(attempt), wait=wait_fixed(3), reraise=True)
    async def get_():
        Logger.debug(f'[GET] {url}')

        if not Config('allow_request_private_ip') and not request_private_ip:
            private_ip_check(url)

        async with aiohttp.ClientSession(headers=headers,
                                         connector=TCPConnector(verify_ssl=False) if debug else None, ) as session:
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout), headers=headers,
                                       proxy=proxy, params=params) as req:
                    Logger.debug(f'[{req.status}] {url}')
                    if logging_resp:
                        Logger.debug(await req.read())
                    if status_code and req.status != status_code:
                        if not logging_resp and logging_err_resp:
                            Logger.error(await req.read())
                        raise ValueError(
                            f'{str(req.status)}[Ke:Image,path=https://http.cat/{str(req.status)}.jpg]')
                    if fmt is not None:
                        if hasattr(req, fmt):
                            return await getattr(req, fmt)()
                        else:
                            raise ValueError(f"NoSuchMethod: {fmt}")
                    else:
                        text = await req.text()
                        return text
            except asyncio.exceptions.TimeoutError:
                raise ValueError(f'Request timeout.')
            except Exception as e:
                Logger.error(f'Error while requesting {url}: {e}')
                raise e

    return await get_()


async def post_url(url: str, data: any = None, status_code: int = False, headers: dict = None, fmt=None, timeout=20,
                   attempt=3, request_private_ip=False, logging_err_resp=True):
    '''发送POST请求。
    :param url: 需要发送的url。
    :param data: 需要发送的数据。
    :param status_code: 指定请求到的状态码，若不符则抛出ValueError。
    :param headers: 请求时使用的http头。
    :param fmt: 指定返回的格式。
    :param timeout: 超时时间。
    :param attempt: 指定请求尝试次数。
    :param request_private_ip: 是否允许请求私有IP。
    :param logging_err_resp: 是否记录错误响应。
    :returns: 发送请求后的响应。'''

    @retry(stop=stop_after_attempt(attempt), wait=wait_fixed(3), reraise=True)
    async def _post():
        Logger.debug(f'[POST] {url}')
        if not Config('allow_request_private_ip') and not request_private_ip:
            private_ip_check(url)

        async with aiohttp.ClientSession(headers=headers,
                                         connector=TCPConnector(verify_ssl=False) if debug else None, ) as session:
            try:
                async with session.post(url, data=data, headers=headers,
                                        timeout=aiohttp.ClientTimeout(total=timeout),
                                        proxy=proxy) as req:
                    Logger.debug(f'[{req.status}] {url}')
                    if logging_resp:
                        Logger.debug(await req.read())
                    if status_code and req.status != status_code:
                        if not logging_resp and logging_err_resp:
                            Logger.error(await req.read())
                        raise ValueError(
                            f'{str(req.status)}[Ke:Image,path=https://http.cat/{str(req.status)}.jpg]')
                    if fmt is not None:
                        if hasattr(req, fmt):
                            return await getattr(req, fmt)()
                        else:
                            raise ValueError(f"NoSuchMethod: {fmt}")
                    else:
                        text = await req.text()
                        return text
            except asyncio.exceptions.TimeoutError:
                raise ValueError(f'Request timeout.')
            except Exception as e:
                Logger.error(f'Error while requesting {url}: {e}')
                raise e

    return await _post()


async def download_to_cache(url: str, filename=None, status_code: int = False, method="GET", post_data=None,
                            headers: dict = None, timeout=20, attempt=3, request_private_ip=False,
                            logging_err_resp=True) -> Union[str, bool]:
    '''利用AioHttp下载指定url的内容，并保存到缓存（默认./cache目录）。

    :param url: 需要获取的url。
    :param filename: 指定保存的文件名，默认为随机文件名。
    :param status_code: 指定请求到的状态码，若不符则抛出ValueError。
    :param method: 指定请求方式。
    :param post_data: 如果指定请求方式为POST，需要传入的数据。
    :param headers: 请求时使用的http头。
    :param timeout: 超时时间。
    :param attempt: 指定请求尝试次数。
    :param request_private_ip: 是否允许请求私有IP。
    :param logging_err_resp: 是否记录错误响应。
    :returns: 文件的相对路径，若获取失败则返回False。'''

    if post_data is not None:
        method = 'POST'

    @retry(stop=stop_after_attempt(attempt), wait=wait_fixed(3), reraise=True)
    async def download_():
        if not Config('allow_request_private_ip') and not request_private_ip:
            private_ip_check(url)

        data = None

        if method.upper() == 'GET':
            data = await get_url(url, status_code=status_code, headers=headers, fmt='read', timeout=timeout, attempt=1,
                                 request_private_ip=request_private_ip, logging_err_resp=logging_err_resp)
        if method.upper() == 'POST':
            data = await post_url(url, data=post_data, status_code=status_code, headers=headers, fmt='read',
                                  timeout=timeout, attempt=1, request_private_ip=request_private_ip,
                                  logging_err_resp=logging_err_resp)

        if data is not None:
            if filename is None:
                ftt = ft.match(data).extension
                path = f'{random_cache_path()}.{ftt}'
            else:
                path = Config("cache_path") + f'/{filename}'
            async with async_open(path, 'wb+') as file:
                await file.write(data)
                return path
        else:
            return False

    return await download_()


__all__ = ['get_url', 'post_url', 'download_to_cache']
