"""基于`httpx`的互联网请求工具，用于让机器人请求外部网站。

请勿在模块中导入`request`库，否则会导致阻塞问题。
"""

import os
import re
import socket
import urllib.parse
import uuid
from http.cookies import SimpleCookie
from typing import Any, Dict, Optional, Union

import filetype as ft
import httpx
from aiofile import async_open
from tenacity import retry, wait_fixed, stop_after_attempt

from core.config import Config
from core.constants.path import cache_path
from core.logger import Logger

logging_resp = False
debug = Config("debug", False)
proxy = Config("proxy", cfg_type=str, secret=True)

url_pattern = re.compile(
    r"\b(?:http[s]?:\/\/)?(?:[a-zA-Z0-9\-\:_@]+\.)+[a-zA-Z]{2,}(?:\/[a-zA-Z0-9-._~:\/?#[\]@!$&\'()*+,;=%]*)?\b"
)

_matcher_private_ips = re.compile(
    r"^(?:127\.|0?10\.|172\.0?1[6-9]\.|172\.0?2[0-9]\.172\.0?3[01]\.|192\.168\.|169\.254\.|::1|[fF][cCdD][0-9a-fA-F]{2}:|[fF][eE][89aAbB][0-9a-fA-F]:)"
)


def private_ip_check(url: str):
    """检查是否为私有IP，若是则抛出ValueError异常。

    :param url: 需要检查的url。"""
    hostname = urllib.parse.urlparse(url).hostname
    addr_info = socket.getaddrinfo(hostname, 80)

    addr = addr_info[0][4][0]
    if _matcher_private_ips.match(addr):
        raise ValueError(
            f"Attempt of requesting private IP addresses is not allowed, requesting {hostname}."
        )


async def get_url(
    url: str,
    status_code: Optional[int] = 200,
    headers: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None,
    fmt: Optional[str] = None,
    timeout: Optional[float] = 20,
    attempt: int = 3,
    request_private_ip: bool = False,
    logging_err_resp: bool = True,
    cookies: Optional[Dict[str, Any]] = None,
) -> Optional[Union[str, dict[str, Any], list[Any], bytes]]:
    """利用httpx获取指定URL的内容。

    :param url: 需要获取的URL。
    :param status_code: 指定请求到的状态码，若不符则抛出ValueError。
    :param headers: 请求时使用的http头。
    :param params: 请求时使用的参数。
    :param fmt: 指定返回的格式。
    :param timeout: 超时时间。
    :param attempt: 指定请求尝试次数。
    :param request_private_ip: 是否允许请求私有IP。
    :param logging_err_resp: 是否记录错误响应。
    :param cookies: 使用的cookies。
    :returns: 指定URL的内容。（字符串）
    """

    @retry(stop=stop_after_attempt(attempt), wait=wait_fixed(3), reraise=True)
    async def get_():
        Logger.debug(f"[GET] {url}")

        if not Config("allow_request_private_ip", False) and not request_private_ip:
            private_ip_check(url)

        async with httpx.AsyncClient(
            headers=headers,
            proxy=proxy,
            verify=not debug
        ) as client:
            if cookies:
                ck = SimpleCookie()
                ck.load(cookies)
                cookies_dict = {key: morsel.value for key, morsel in ck.items()}
                client.cookies.update(cookies_dict)
                Logger.debug(f"Using cookies: {cookies_dict}")
            try:
                resp = await client.get(
                    url,
                    timeout=timeout,
                    headers=headers,
                    params=params,
                    follow_redirects=True,
                )
                Logger.debug(f"[{resp.status_code}] {url}")
                if logging_resp:
                    Logger.debug(resp.text)
                if status_code and resp.status_code != status_code:
                    if not logging_resp and logging_err_resp:
                        Logger.error(resp.text)
                    raise ValueError(
                        f"{str(resp.status_code)}[Ke:Image,path=https://http.cat/{str(resp.status_code)}.jpg]"
                    )
                if fmt:
                    if hasattr(resp, fmt):
                        attr = getattr(resp, fmt)
                        if callable(attr):
                            return attr()
                        return attr
                    raise ValueError(f"NoSuchMethod: {fmt}")
                return resp.text
            except (httpx.ConnectError, httpx.TimeoutException):
                raise ValueError("Request timeout")
            except Exception as e:
                if logging_err_resp:
                    Logger.error(f"Error while requesting {url}: \n{e}")
                raise e

    return await get_()


async def post_url(
    url: str,
    data: Any = None,
    status_code: Optional[int] = 200,
    headers: Optional[Dict[str, Any]] = None,
    fmt: Optional[str] = None,
    timeout: Optional[float] = 20,
    attempt: int = 3,
    request_private_ip: bool = False,
    logging_err_resp: bool = True,
    cookies: Optional[Dict[str, Any]] = None,
) -> Optional[Union[str, dict[str, Any], list[Any], bytes]]:
    """利用httpx发送POST请求。

    :param url: 需要发送的URL。
    :param data: 需要发送的数据。
    :param status_code: 指定请求到的状态码，若不符则抛出ValueError。
    :param headers: 请求时使用的http头。
    :param fmt: 指定返回的格式。
    :param timeout: 超时时间。
    :param attempt: 指定请求尝试次数。
    :param request_private_ip: 是否允许请求私有IP。
    :param logging_err_resp: 是否记录错误响应。
    :param cookies: 使用的 cookies。
    :returns: 指定URL的内容。（字符串）
    """

    @retry(stop=stop_after_attempt(attempt), wait=wait_fixed(3), reraise=True)
    async def _post():
        Logger.debug(f"[POST] {url}")
        if not Config("allow_request_private_ip", False) and not request_private_ip:
            private_ip_check(url)

        async with httpx.AsyncClient(
            headers=headers,
            proxy=proxy,
            verify=not debug
        ) as client:
            if cookies:
                ck = SimpleCookie()
                ck.load(cookies)
                cookies_dict = {key: morsel.value for key, morsel in ck.items()}
                client.cookies.update(cookies_dict)
                Logger.debug(f"Using cookies: {cookies_dict}")
            try:
                resp = await client.post(
                    url,
                    data=data,
                    headers=headers,
                    timeout=timeout,
                    follow_redirects=True,
                )
                Logger.debug(f"[{resp.status_code}] {url}")
                if logging_resp:
                    Logger.debug(resp.text)
                if status_code and resp.status_code != status_code:
                    if not logging_resp and logging_err_resp:
                        Logger.error(resp.text)
                    raise ValueError(
                        f"{str(resp.status_code)}[Ke:Image,path=https://http.cat/{str(resp.status_code)}.jpg]"
                    )
                if fmt:
                    if hasattr(resp, fmt):
                        attr = getattr(resp, fmt)
                        if callable(attr):
                            return attr()
                        return attr
                    raise ValueError(f"NoSuchMethod: {fmt}")
                return resp.text
            except (httpx.ConnectError, httpx.TimeoutException):
                raise ValueError("Request timeout")
            except Exception as e:
                if logging_err_resp:
                    Logger.error(f"Error while requesting {url}: {e}")
                raise e

    return await _post()


async def download(
    url: str,
    filename: Optional[str] = None,
    path: Optional[str] = None,
    status_code: Optional[int] = 200,
    method: str = "GET",
    post_data: Any = None,
    headers: Optional[Dict[str, Any]] = None,
    timeout: Optional[float] = 20,
    attempt: int = 3,
    request_private_ip: bool = False,
    logging_err_resp: bool = True,
) -> Union[str, bool]:
    """利用httpx下载指定url的内容，并保存到指定目录。

    :param url: 需要获取的URL。
    :param filename: 指定保存的文件名，默认为随机文件名。
    :param path: 指定目录，默认为缓存目录。
    :param status_code: 指定请求到的状态码，若不符则抛出ValueError。
    :param method: 指定请求方式。
    :param post_data: 如果指定请求方式为POST，需要传入的数据。
    :param headers: 请求时使用的http头。
    :param timeout: 超时时间。
    :param attempt: 指定请求尝试次数。
    :param request_private_ip: 是否允许请求私有IP。
    :param logging_err_resp: 是否记录错误响应。
    :returns: 文件的相对路径，若获取失败则返回False。
    """

    if post_data is not None:
        method = "POST"

    @retry(stop=stop_after_attempt(attempt), wait=wait_fixed(3), reraise=True)
    async def download_(filename=filename, path=path):
        if not Config("allow_request_private_ip", False) and not request_private_ip:
            private_ip_check(url)

        data = None
        if method.upper() == "GET":
            data = await get_url(
                url,
                status_code=status_code,
                headers=headers,
                fmt="read",
                timeout=timeout,
                attempt=1,
                request_private_ip=request_private_ip,
                logging_err_resp=logging_err_resp,
            )
        if method.upper() == "POST":
            data = await post_url(
                url,
                data=post_data,
                status_code=status_code,
                headers=headers,
                fmt="read",
                timeout=timeout,
                attempt=1,
                request_private_ip=request_private_ip,
                logging_err_resp=logging_err_resp,
            )

        if data:
            if not filename:
                try:
                    ftt = ft.match(data).extension
                except AttributeError:
                    ftt = "txt"
                filename = f"{str(uuid.uuid4())}.{ftt}"
            if not path:
                path = cache_path
            path = os.path.join(path, filename)
            async with async_open(path, "wb+") as file:
                await file.write(data)
                return path
        else:
            return False

    return await download_()


download_to_cache = download


__all__ = ["get_url", "post_url", "download", "url_pattern"]
