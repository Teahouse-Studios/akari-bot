import re

from core.builtins import Bot, Image
from core.component import module
from .bugtracker import bugtracker_get, make_screenshot

bug = module('bugtracker', alias='bug', developers=['OasisAkari'])


@bug.command('<MojiraID> {{bugtracker.help}}')
async def bugtracker(msg: Bot.MessageSession):
    mojira_id = msg.parsed_msg['<MojiraID>']
    if mojira_id:
        q = re.match(r'(.*-.*)', mojira_id)
        if q:
            result = await bugtracker_get(msg, q.group(1))
            await msg.send_message(result[0])
            if result[1] is not None:
                screenshot = await make_screenshot(result[1])
                if screenshot:
                    await msg.send_message(Image(screenshot))


@bug.regex(pattern=r'\!?(BDS|MCPE|MCD|MCL|MCLG|REALMS|MC|WEB)-(\d+)\b', mode='M', flags=re.I,
           desc='{bugtracker.help.regex.desc}')
async def regex_bugtracker(msg: Bot.MessageSession):
    matched_msg = msg.matched_msg
    if len(matched_msg.group(1)) < 10:
        result = await bugtracker_get(msg, matched_msg.group(1) + '-' + matched_msg.group(2))
        await msg.send_message(result[0])
        if result[1] is not None:
            screenshot = await make_screenshot(result[1])
            if screenshot:
                await msg.send_message(Image(screenshot))


@bug.regex(re.compile(r'https?://bugs\.mojang\.com/(?:browse/((?:BDS|MCPE|MCD|MCL|MCLG|REALMS|MC|WEB)-\d*)'
                      r'|projects/.*?/issues/((?:BDS|MCPE|MCD|MCL|MCLG|REALMS|MC|WEB)-\d*))', flags=re.I),
           mode='A', desc='{bugtracker.help.regex.url}')
async def _(msg: Bot.MessageSession):
    async def bgtask(msg: Bot.MessageSession):
        for title in msg.matched_msg:
            for t in title:
                if t != '':
                    get_ = await bugtracker_get(msg, t.split('?')[0], nolink=True)
                    await msg.send_message(get_[0])
                    if get_[1] is not None:
                        screenshot = await make_screenshot(get_[1])
                        if screenshot:
                            await msg.send_message(Image(screenshot))

    await bgtask(msg)
