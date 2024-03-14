import base64
import traceback
from typing import List, Union

import aiohttp
import filetype as ft
import ujson as json
from PIL import Image as PImage
from aiofile import async_open

from core.builtins import Plain, Image, Voice, Embed, MessageChain, MessageSession
from core.logger import Logger
from core.utils.cache import random_cache_path
from core.utils.http import download_to_cache
from core.utils.web_render import WebRender, webrender


async def image_split(i: Image) -> List[Image]:
    i = PImage.open(await i.get())
    iw, ih = i.size
    if ih <= 1500:
        return [Image(i)]
    _h = 0
    i_list = []
    for x in range((ih // 1500) + 1):
        if _h + 1500 > ih:
            crop_h = ih
        else:
            crop_h = _h + 1500
        i_list.append(Image(i.crop((0, _h, iw, crop_h))))
        _h = crop_h
    return i_list


def get_fontsize(font, text):
    left, top, right, bottom = font.getbbox(text)
    return right - left, bottom - top


save_source = True


async def msgchain2image(message_chain: Union[List, MessageChain], msg: MessageSession = None, use_local=True):
    '''使用Webrender将消息链转换为图片。

    :param message_chain: 消息链或消息链列表。
    :param use_local: 是否使用本地Webrender渲染。
    :return: 图片的相对路径，若渲染失败则返回False。
    '''
    if not WebRender.status:
        return False
    elif not WebRender.local:
        use_local = False
    if isinstance(message_chain, List):
        message_chain = MessageChain(message_chain)
    lst = []
    html_template = """<!DOCTYPE html>
<html lang="en">
<head>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+HK&family=Noto+Sans+JP&family=Noto+Sans+KR&family=Noto+Sans+SC&family=Noto+Sans+TC&display=swap" rel="stylesheet">
    <style>html body {
        margin-top: 0px !important;
        font-family: 'Noto Sans SC', sans-serif;
    }

    :lang(ko) {
        font-family: 'Noto Sans KR', 'Noto Sans JP', 'Noto Sans HK', 'Noto Sans TC', 'Noto Sans SC', sans-serif;
    }

    :lang(ja) {
        font-family: 'Noto Sans JP', 'Noto Sans HK', 'Noto Sans TC', 'Noto Sans SC', 'Noto Sans KR', sans-serif;
    }

    :lang(zh-TW) {
        font-family: 'Noto Sans HK', 'Noto Sans TC', 'Noto Sans JP', 'Noto Sans SC', 'Noto Sans KR', sans-serif;
    }

    :lang(zh-HK) {
        font-family: 'Noto Sans HK', 'Noto Sans TC', 'Noto Sans JP', 'Noto Sans SC', 'Noto Sans KR', sans-serif;
    }

    :lang(zh-Hans), :lang(zh-CN), :lang(zh) {
        font-family:  'Noto Sans SC', 'Noto Sans HK', 'Noto Sans TC', 'Noto Sans JP', 'Noto Sans KR', sans-serif;
    }</style>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Document</title>
</head>
<body>
    <div class="botbox"'>
    ${content}
    </div>
</body>
</html>"""

    for m in message_chain.as_sendable(msg=msg, embed=False):
        if isinstance(m, Plain):
            lst.append('<div>' + m.text.replace('\n', '<br>') + '</div>')
        if isinstance(m, Image):
            async with async_open(await m.get(), 'rb') as fi:
                data = await fi.read()
                try:
                    ftt = ft.match(data)
                    lst.append(f'<img src="data:{ftt.mime};base64,{
                        (base64.encodebytes(data)).decode("utf-8")}" width="720" />')
                except TypeError:
                    traceback.print_exc()
        if isinstance(m, Voice):
            lst.append('<div>[Voice]</div>')
        if isinstance(m, Embed):
            lst.append('<div>[Embed]</div>')

    pic = False

    d = {'content': html_template.replace('${content}', '\n'.join(lst)), 'element': '.botbox'}

    html_ = json.dumps(d)

    fname = random_cache_path() + '.html'
    with open(fname, 'w', encoding='utf-8') as fi:
        fi.write(d['content'])

    try:
        pic = await download_to_cache(webrender('element_screenshot', use_local=use_local),
                                      status_code=200,
                                      headers={'Content-Type': 'application/json'},
                                      method="POST",
                                      post_data=html_,
                                      attempt=1,
                                      timeout=30,
                                      request_private_ip=True
                                      )
    except aiohttp.ClientConnectorError:
        if use_local:
            pic = await download_to_cache(webrender('element_screenshot', use_local=False),
                                            status_code=200,
                                            method='POST',
                                            headers={'Content-Type': 'application/json'},
                                            post_data=html_,
                                            request_private_ip=True
                                            )
        else:
            Logger.info('[Webrender] Generation Failed.')
            return False
    return pic


async def svg_render(file_path: str, use_local=True):
    '''使用Webrender渲染svg文件。

    :param message_chain: svg文件路径。
    :param use_local: 是否使用本地Webrender渲染。
    :return: 图片的相对路径，若渲染失败则返回False。
    '''
    if not WebRender.status:
        return False
    elif not WebRender.local:
        use_local = False

    html_template = """<!DOCTYPE html>
<html lang="en">
<head>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+HK&family=Noto+Sans+JP&family=Noto+Sans+KR&family=Noto+Sans+SC&family=Noto+Sans+TC&display=swap" rel="stylesheet">
    <style>html body {
        margin-top: 0px !important;
        font-family: 'Noto Sans SC', sans-serif;
    }

    :lang(ko) {
        font-family: 'Noto Sans KR', 'Noto Sans JP', 'Noto Sans HK', 'Noto Sans TC', 'Noto Sans SC', sans-serif;
    }

    :lang(ja) {
        font-family: 'Noto Sans JP', 'Noto Sans HK', 'Noto Sans TC', 'Noto Sans SC', 'Noto Sans KR', sans-serif;
    }

    :lang(zh-TW) {
        font-family: 'Noto Sans HK', 'Noto Sans TC', 'Noto Sans JP', 'Noto Sans SC', 'Noto Sans KR', sans-serif;
    }

    :lang(zh-HK) {
        font-family: 'Noto Sans HK', 'Noto Sans TC', 'Noto Sans JP', 'Noto Sans SC', 'Noto Sans KR', sans-serif;
    }

    :lang(zh-Hans), :lang(zh-CN), :lang(zh) {
        font-family:  'Noto Sans SC', 'Noto Sans HK', 'Noto Sans TC', 'Noto Sans JP', 'Noto Sans KR', sans-serif;
    }
    .botbox {
        display: inline-block;
        width: fit-content;
        height: fit-content;
    }

    .botbox svg {
        width: 100%;
        height: 100%;
        }</style>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>File</title>
</head>
<body>
    <div class="botbox"'>
    ${content}
    </div>
</body>
</html>"""

    with open(file_path, 'r') as file:
        svg_content = file.read()

    pic = False

    d = {'content': html_template.replace('${content}', svg_content), 'element': '.botbox', 'counttime': False}

    html_ = json.dumps(d)

    fname = random_cache_path() + '.html'
    with open(fname, 'w', encoding='utf-8') as fi:
        fi.write(d['content'])

    try:
        pic = await download_to_cache(webrender('element_screenshot', use_local=use_local),
                                      status_code=200,
                                      headers={'Content-Type': 'application/json'},
                                      method="POST",
                                      post_data=html_,
                                      attempt=1,
                                      timeout=30,
                                      request_private_ip=True
                                      )
    except aiohttp.ClientConnectorError:
        if use_local:
            pic = await download_to_cache(webrender('element_screenshot', use_local=False),
                                          status_code=200,
                                          method='POST',
                                          headers={'Content-Type': 'application/json'},
                                          post_data=html_,
                                          request_private_ip=True
                                          )
        else:
            Logger.info('[Webrender] Generation Failed.')
            return False
    return pic
