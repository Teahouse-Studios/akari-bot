import re

from graia.application import MessageChain
from graia.application.message.elements.internal import Plain

from core.template import sendMessage
from .bugtracker import bug


async def bugtracker(kwargs: dict):
    msg = kwargs['trigger_msg']
    msg = re.sub('bug ', '', msg)
    q = re.match(r'(.*)\-(.*)', msg)
    if q:
        result = await bug(q.group(1) + '-' + q.group(2))
        msgchain = MessageChain.create([Plain(result)])
        await sendMessage(kwargs, msgchain)


async def regex_bugtracker(kwargs: dict):
    msg = kwargs[MessageChain].asDisplay()
    if msg.find('[Webhook]') != -1:
        return
    if msg[0] == '!':
        msg = re.sub('!', '', msg)
        msg = re.sub('bug ', '', msg)
        q = re.match(r'(.*)\-(.*)', msg)
        if q:
            result = await bug(q.group(1) + '-' + q.group(2))
            msgchain = MessageChain.create([Plain(result)])
            await sendMessage(kwargs, msgchain)
    findlink = re.findall(r'(https://bugs.mojang.com/browse/.*?-\d*)', msg)
    for link in findlink:
        print(link)
        matchbug = re.match(r'https://bugs.mojang.com/browse/(.*?-\d*)', link)
        if matchbug:
            await sendMessage(kwargs, await bug(matchbug.group(1)))


command = {'bug': bugtracker}
regex = {'bug_regex': regex_bugtracker}
help = {'bug': {'module': '查询Mojira上的漏洞编号。', 'help': '~bug <mojiraid> 查询Mojira上的漏洞编号。'},
        'bug_regex': {'module': '正则自动查询Mojira上的漏洞编号。',
                      'help': '提示：正则自动查询Mojira漏洞已开启，所有消息开头为!<mojiraid>和来自Mojira的链接将会被自动查询并发送梗概内容。'}}
