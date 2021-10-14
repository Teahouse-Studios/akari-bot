import re

from core.elements import MessageSession
from core.decorator import on_command, on_regex
from .bugtracker import bugtracker_get


@on_command('bug', alias='b', help_doc='~bug <MojiraID> {查询Mojira上的漏洞编号内容}',
            developers=['OasisAkari'], allowed_none=False)
async def bugtracker(msg: MessageSession):
    mojira_id = msg.parsed_msg['<MojiraID>']
    if mojira_id:
        q = re.match(r'(.*-.*)', mojira_id)
        if q:
            result = await bugtracker_get(q.group(1))
            await msg.sendMessage(result)


@on_regex('bug_regex', pattern=r'^\!(?:bug |)(.*)-(.*)', mode='M',
          desc='正则自动查询Mojira漏洞，所有消息开头为!<mojiraid>和来自Mojira的链接将会被自动查询并发送梗概内容。',
          developers=['OasisAkari'])
async def regex_bugtracker(msg: MessageSession):
    result = await bugtracker_get(msg.matched_msg.group(1) + '-' + msg.matched_msg.group(2))
    return await msg.sendMessage(result)


"""rlink = re.compile(r'https://bugs\.mojang\.com/browse/(.*?-\d*)')
    findlink = re.findall(rlink, display_msg)
    for link in findlink:
        matchbug = re.match(rlink, link)
        if matchbug:
            await msg.sendMessage(await bugtracker_get(matchbug.group(1)))"""
