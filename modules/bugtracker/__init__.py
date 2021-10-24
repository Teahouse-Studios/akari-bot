import re

from core.elements import MessageSession
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
            await msg.sendMessage(result)


rbug = on_regex('bug_regex',
                desc='正则自动查询Mojira漏洞，所有消息开头为!<mojiraid>和来自Mojira的链接将会被自动查询并发送梗概内容。',
                developers=['OasisAkari'])


@rbug.handle(pattern=r'^\!(?:bug |)(.*)-(.*)', mode='M')
async def regex_bugtracker(msg: MessageSession):
    result = await bugtracker_get(msg.matched_msg.group(1) + '-' + msg.matched_msg.group(2))
    return await msg.sendMessage(result)


"""rlink = re.compile(r'https://bugs\.mojang\.com/browse/(.*?-\d*)')
    findlink = re.findall(rlink, display_msg)
    for link in findlink:
        matchbug = re.match(rlink, link)
        if matchbug:
            await msg.sendMessage(await bugtracker_get(matchbug.group(1)))"""
