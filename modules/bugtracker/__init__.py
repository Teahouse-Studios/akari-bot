import asyncio
import re

from core.builtins import Bot
from core.component import on_command, on_regex
from core.utils.i18n import get_target_locale
from .bugtracker import bugtracker_get

bug = on_command('bug', alias='b', developers=['OasisAkari'])


@bug.handle('<MojiraID> {{bug.desc}}')
async def bugtracker(msg: Bot.MessageSession):
    lang = get_target_locale(msg)
    mojira_id = msg.parsed_msg['<MojiraID>']
    if mojira_id:
        q = re.match(r'(.*-.*)', mojira_id)
        if q:
            result = await bugtracker_get(q.group(1))
            await msg.finish(result)


lang = get_target_locale(msg)
rbug = on_regex('bug_regex',
                desc=f'{lang.t("bug_regex.help")}',
                developers=['OasisAkari'])


@rbug.handle(pattern=r'^\!(?:bug |)(.*)-(.*)', mode='M')
async def regex_bugtracker(msg: Bot.MessageSession):
    matched_msg = msg.matched_msg
    if len(matched_msg.group(1)) < 10 and len(matched_msg.group(2)) < 10:
        result = await bugtracker_get(matched_msg.group(1) + '-' + matched_msg.group(2))
        await msg.finish(result)


@rbug.handle(re.compile(r'https://bugs\.mojang\.com/browse/(.*?-\d*)'), mode='A')
async def _(msg: Bot.MessageSession):
    async def bgtask(msg: Bot.MessageSession):
        for title in msg.matched_msg:
            await msg.sendMessage(await bugtracker_get(title, nolink=True))

    asyncio.create_task(bgtask(msg))
