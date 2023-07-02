import re

from core.builtins import Bot
from core.component import module
from .bilibili import get_info


api_url = f'https://api.bilibili.com/x/web-interface/view/detail'


bili = module('bilibili', alias='bili', developers=['DoroWolf'],
              desc='{bilibili.help.desc}', support_languages=['zh_cn'])


@bili.command('<video> [-i] {{bilibili.help}}',
          options_desc={'-i': '{bilibili.help.option.i}'})
async def _(msg: Bot.MessageSession, video: str):
    get_detail = False
    if msg.parsed_msg.get('-i', False):
        get_detail = True
    if video[:2].upper() == "BV":
        url = f"{api_url}?bvid={video}"
    elif video[:2].lower() == "av":
        url = f"{api_url}?aid={video[2:]}"
    else:
        msg.finish(msg.locale.t('bilibili.message.error.invalid'))
    get_info(msg, url, get_detail)


@bili.handle(re.compile(r"([aA][vV])(\d+)"),
            desc="{bilibili.help.regex.av}")
async def _(msg: Bot.MessageSession):
    res = msg.matched_msg
    if res:
        url = f"{api_url}?aid={res.groups()[1]}"
    get_info(msg, url)


@bili.handle(re.compile(r"(BV1[a-zA-Z0-9]{9})"),
            desc="{bilibili.help.regex.bv}")
async def _(msg: Bot.MessageSession):
    res = msg.matched_msg
    if res:
        url = f"{api_url}?bvid={res}"
    get_info(msg, url)