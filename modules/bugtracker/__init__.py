import asyncio
import re

from core.builtins import Bot
from core.component import module
from core.utils.i18n import get_target_locale
from .bugtracker import bugtracker_get

bug = module('bug', alias='b', developers=['OasisAkari'])


@bug.handle('<MojiraID> {{bug.desc}}')
async def bugtracker(msg: Bot.MessageSession):
    mojira_id = msg.parsed_msg['<MojiraID>']
    if mojira_id:
        q = re.match(r'(.*-.*)', mojira_id)
        if q:
            result = await bugtracker_get(q.group(1))
            await msg.finish(result)


@bug.regex(pattern=r'^\!(?:bug |)(.*)-(.*)', mode='M')
async def regex_bugtracker(msg: Bot.MessageSession):
    matched_msg = msg.matched_msg
    if len(matched_msg.group(1)) < 10 and len(matched_msg.group(2)) < 10:
        result = await bugtracker_get(matched_msg.group(1) + '-' + matched_msg.group(2))
        await msg.finish(result)


@bug.regex(re.compile(r'https://bugs\.mojang\.com/browse/(.*?-\d*)'), mode='A')
async def _(msg: Bot.MessageSession):
    async def bgtask(msg: Bot.MessageSession):
        for title in msg.matched_msg:
            await msg.sendMessage(await bugtracker_get(title, nolink=True))

    asyncio.create_task(bgtask(msg))
