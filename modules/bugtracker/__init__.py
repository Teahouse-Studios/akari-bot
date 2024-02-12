import re

from core.builtins import Bot, Image, Plain
from core.component import module
from .bugtracker import bugtracker_get, make_screenshot

bug = module('bugtracker', alias='bug', developers=['OasisAkari'])


@bug.command('<mojiraid> {{bugtracker.help}}')
async def bugtracker(msg: Bot.MessageSession, mojiraid: str):
    if mojiraid:
        q = re.match(r'(.*-.*)', mojiraid)
        if q:
            result = await bugtracker_get(msg, q.group(1))
            await msg.send_message(result[0])
            if result[1]:
                screenshot = await make_screenshot(result[1])
                if screenshot:
                    await msg.finish(Image(screenshot))
                else:
                    await msg.finish()


@bug.regex(=r'((?:BDS|MCPE|MCD|MCL|MCLG|REALMS|MC|WEB)-\d*)', mode='A', flags=re.I,
           desc='{bugtracker.help.regex.desc}')
async def regex_bugtracker(msg: Bot.MessageSession):
    msg_list = []
    for title in msg.matched_msg:
        if title != '':
            get_ = await bugtracker_get(msg, title)
            msg_list.append(get_)
    await msg.send_message([q[0] for q in msg_list])
    if len(msg_list) == 1:
        screenshot = await make_screenshot(msg_list[0][1])
        if screenshot:
            await msg.finish(Image(screenshot))
        else:
            await msg.finish()


@bug.regex(re.compile(r'https?://bugs\.mojang\.com/(?:browse/((?:BDS|MCPE|MCD|MCL|MCLG|REALMS|MC|WEB)-\d*)'
                      r'|projects/.*?/issues/((?:BDS|MCPE|MCD|MCL|MCLG|REALMS|MC|WEB)-\d*))', flags=re.I),
           mode='A', desc='{bugtracker.help.regex.url}')
async def _(msg: Bot.MessageSession):
    msg_list = []
    for title in msg.matched_msg:
        if title != '':
            get_ = await bugtracker_get(msg, title[0], nolink=True)
            msg_list.append(get_)
    await msg.send_message([q[0] for q in msg_list])
    if len(msg_list) == 1:
        screenshot = await make_screenshot(msg_list[0][1])
        if screenshot:
            await msg.finish(Image(screenshot))
        else:
            await msg.finish()