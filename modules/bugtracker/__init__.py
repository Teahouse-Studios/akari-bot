import asyncio
import re

from core.builtins import Bot
from core.component import on_command, on_regex
from .bugtracker import bugtracker_get

bug = on_command('bug', alias='b', developers=['OasisAkari'])


@bug.handle('<MojiraID> {查询 Mojira 上的漏洞编号内容。}')
async def bugtracker(msg: Bot.MessageSession):
    mojira_id = msg.parsed_msg['<MojiraID>']
    if mojira_id:
        q = re.match(r'(.*-.*)', mojira_id)
        if q:
            result = await bugtracker_get(q.group(1))
            await msg.finish(result)


rbug = on_regex('bug_regex',
                desc='开启后发送 !<mojiraid> 将会查询 Mojira 并发送该漏洞的梗概内容。',
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
