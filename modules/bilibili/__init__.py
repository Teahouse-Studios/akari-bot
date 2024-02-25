import re
from urllib.parse import urlparse

import aiohttp

from core.builtins import Bot
from core.component import module
from .bili_api import get_video_info

bili = module('bilibili', alias='bili', developers=['DoroWolf'],
              desc='{bilibili.help.desc}', support_languages=['zh_cn'])


@bili.command('<bid> [-i] {{bilibili.help}}',
              options_desc={'-i': '{bilibili.help.option.i}'},
              exclude_from=['Discord|Channel'])
@bili.command('<bid> {{bilibili.help}}', available_for=['Discord|Channel'])
async def _(msg: Bot.MessageSession, bid: str, get_detail = False):
    if msg.parsed_msg.get('-i', False):
        get_detail = True
    if bid[:2].upper() == "BV":
        query = f"?bvid={bid}"
    elif bid[:2].upper() == "AV":
        query = f"?aid={bid[2:]}"
    else:
        return await msg.finish(msg.locale.t('bilibili.message.invalid'))
    res = await get_video_info(msg, query, get_detail)
    if res:
        await msg.finish(msg.locale.t('message.cooldown', time=int(res), cd_time=30))


@bili.regex(re.compile(r"av(\d+)", flags=re.I), mode='A', desc="{bilibili.help.regex.av}")
async def _(msg: Bot.MessageSession):
    query = f"?aid={msg.matched_msg[0]}"
    await get_video_info(msg, query)


@bili.regex(re.compile(r"BV[a-zA-Z0-9]{10}"), mode='A', desc="{bilibili.help.regex.bv}")
async def _(msg: Bot.MessageSession):
    query = f"?bvid={msg.matched_msg[0]}"
    await get_video_info(msg, query)


@bili.regex(
    re.compile(r"https?://(?:bili(?:22|33|2233)\.cn|b23\.tv)/([A-Za-z0-9]{7})(?:/.*?|)"),
    mode="A",
    desc="{bilibili.help.regex.url}")
async def _(msg: Bot.MessageSession):
    video = msg.matched_msg[0]
    query = await parse_shorturl(f"https://b23.tv/{video}")
    if not query:
        return
    await get_video_info(msg, query)


async def parse_shorturl(shorturl):
    async with aiohttp.ClientSession() as session:
        async with session.get(shorturl, allow_redirects=False) as response:
            target_url = response.headers.get('Location')

    video = re.search(r'/video/([^/?]+)', target_url)
    if video:
        return f"?bvid={video.group(1)}"
    else:
        return False
