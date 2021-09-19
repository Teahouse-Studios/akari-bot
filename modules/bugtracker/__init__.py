import re

from core.elements import MessageSession
from core.loader.decorator import command
from .bugtracker import bugtracker_get


@command('bug', alias='b', help_doc='~bug <MojiraID> {查询Mojira上的漏洞编号内容}',
         developers=['OasisAkari'], allowed_none=False)
async def bugtracker(msg: MessageSession):
    mojira_id = msg.parsed_msg['<MojiraID>']
    if mojira_id:
        q = re.match(r'(.*-.*)', mojira_id)
        if q:
            result = await bugtracker_get(q.group(1))
            await msg.sendMessage(result)


@command('bug_regex', desc='正则自动查询Mojira漏洞，所有消息开头为!<mojiraid>和来自Mojira的链接将会被自动查询并发送梗概内容。',
         developers=['OasisAkari'],
         is_regex_function=True)
async def regex_bugtracker(msg: MessageSession):
    display_msg = msg.asDisplay()
    if display_msg.find('[Webhook]') != -1:
        return
    if display_msg[0] == '!':
        display_msg = re.sub('^!', '', display_msg)
        display_msg = re.sub('^bug ', '', display_msg)
        q = re.match(r'(.*-.*)', display_msg)
        if q:
            async with msg.Typing(msg):
                result = await bugtracker_get(q.group(1))
                return await msg.sendMessage(result)
    rlink = re.compile(r'https://bugs\.mojang\.com/browse/(.*?-\d*)')
    findlink = re.findall(rlink, display_msg)
    for link in findlink:
        matchbug = re.match(rlink, link)
        if matchbug:
            await msg.sendMessage(await bugtracker_get(matchbug.group(1)))
