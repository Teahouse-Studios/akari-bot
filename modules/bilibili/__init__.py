import re
from urllib.parse import urlparse

import aiohttp

from core.builtins import Bot
from core.component import module
from .bilibili import get_info

api_url = f'https://api.bilibili.com/x/web-interface/view/detail'

bili = module('bilibili', alias='bili', developers=['DoroWolf'],
              desc='{bilibili.help.desc}', support_languages=['zh_cn'])


@bili.command('<video> [-i] {{bilibili.help}}',
              options_desc={'-i': '{bilibili.help.option.i}'})
async def _(msg: Bot.MessageSession, video: str, get_detail=False):
    if msg.parsed_msg.get('-i', False):
        get_detail = True
    if video[:2].upper() == "BV":
        url = f"{api_url}?bvid={video}"
    elif video[:2].upper() == "AV":
        url = f"{api_url}?aid={video[2:]}"
    else:
        return await msg.finish(msg.locale.t('bilibili.message.error.invalid'))
    await get_info(msg, url, get_detail)


@bili.handle(re.compile(r"AV(\d+)", flags=re.I), mode='M', desc="{bilibili.help.regex.av}")
async def _(msg: Bot.MessageSession):
    res = msg.matched_msg
    url = f"{api_url}?aid={res.groups()[0]}"
    await get_info(msg, url, get_detail=False)


@bili.handle(re.compile(r"BV[a-zA-Z0-9]{10}"), mode='M', desc="{bilibili.help.regex.bv}")
async def _(msg: Bot.MessageSession):
    res = msg.matched_msg
    url = f"{api_url}?bvid={res.group()}"
    await get_info(msg, url, get_detail=False)


@bili.handle(
    re.compile(r"https?://(?:www\.|m\.)?bilibili\.com(?:/video|)/(av\d+|BV[A-Za-z0-9]{10})(?:/.*?|)$"),
    mode="M",
    desc="{bilibili.help.regex.url}")
async def _(msg: Bot.MessageSession):
    video = msg.matched_msg.group(1)
    if video[:2] == "BV":
        url = f"{api_url}?bvid={video}"
    else:
        url = f"{api_url}?aid={video[2:]}"

    await get_info(msg, url, get_detail=False)


@bili.handle(re.compile(r"https?://b23\.tv/(av\d+|BV[A-Za-z0-9]{10}|[A-Za-z0-9]{7})(?:/.*?|)$"), mode="M",
             desc="{bilibili.help.regex.shorturl}")
async def _(msg: Bot.MessageSession):
    res = msg.matched_msg
    video = res.groups()[0]
    if video[:2] == "BV":
        url = f"{api_url}?bvid={video}"
    elif video[:2] == "av":
        url = f"{api_url}?aid={video[2:]}"
    else:
        ...
#        url = await parse_shorturl(f"https://b23.tv/{video}")

    await get_info(msg, url, get_detail=False)


"""
async def parse_shorturl(shorturl):
    async with aiohttp.ClientSession() as session:
        async with session.get(shorturl, allow_redirects=True) as response:
            target_url = str(response.url)
            parsed_url = urlparse(target_url)
            video = parsed_url.path.split("/")[-2]
            url = f"{api_url}?bvid={video}"
            return url
"""