import re

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
    elif video[:2].lower() == "av":
        url = f"{api_url}?aid={video[2:]}"
    else:
        await msg.finish(msg.locale.t('bilibili.message.error.invalid'))
    await get_info(msg, url, get_detail)


@bili.handle(re.compile(r"([aA][vV])(\d+)"),
            desc="{bilibili.help.regex.av}")
async def _(msg: Bot.MessageSession):
    res = msg.matched_msg
    if res:
        url = f"{api_url}?aid={res.groups()[1]}"
    await get_info(msg, url, get_detail=False)


@bili.handle(re.compile(r"(BV[a-zA-Z0-9]{10})"),
            desc="{bilibili.help.regex.bv}")
async def _(msg: Bot.MessageSession):
    res = msg.matched_msg
    if res:
        url = f"{api_url}?bvid={res.group()}"
    await get_info(msg, url, get_detail=False)


@bili.handle(re.compile(r"b23\.tv/(av\d{1,9}|BV[A-Za-z0-9]{10}|[A-Za-z0-9]{7})"),
            desc="{bilibili.help.regex.url}")
async def _(msg: Bot.MessageSession):
    res = msg.matched_msg
    if res:
        video = res.groups()[0]
        if video[:2] == "BV":
            url = f"{api_url}?bvid={video}"
        elif video[:2] == "av":
            url = f"{api_url}?aid={video[2:]}"
        else:
            ...
            
    await get_info(msg, url, get_detail=False)
