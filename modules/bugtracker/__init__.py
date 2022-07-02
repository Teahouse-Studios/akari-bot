import re

from core.builtins.message import MessageSession
from core.component import on_command, on_regex
from .bugtracker import bugtracker_get

bug = on_command('bug', alias='b', developers=['OasisAkari'])


@bug.handle('<MojiraID> {查询Mojira上的漏洞编号内容}')
async def bugtracker(msg: MessageSession):
    mojira_id = msg.parsed_msg['<MojiraID>']
    if mojira_id:
        q = re.match(r'(.*-.*)', mojira_id)
        if q:
            result = await bugtracker_get(q.group(1))
            await msg.finish(result)


rbug = on_regex('bug_regex',
                desc='开启后发送 !<mojiraid> 将会查询Mojira并发送该bug的梗概内容。',
                developers=['OasisAkari'])


@rbug.handle(pattern=r'^\!(?:bug |)(.*)-(.*)', mode='M')
async def regex_bugtracker(msg: MessageSession):
    matched_msg = msg.matched_msg
    if len(matched_msg.group(1)) < 10 and len(matched_msg.group(2)) < 10:
        result = await bugtracker_get(matched_msg.group(1) + '-' + matched_msg.group(2))
        await msg.finish(result)


"""rlink = re.compile(r'https://bugs\.mojang\.com/browse/(.*?-\d*)')
    findlink = re.findall(rlink, display_msg)
    for link in findlink:
        matchbug = re.match(rlink, link)
        if matchbug:
            await msg.sendMessage(await bugtracker_get(matchbug.group(1)))"""
