import asyncio
import re

from core.dirty_check import check
from core.template import sendMessage, revokeMessage
from .server import server


async def main(kwargs: dict):
    message = kwargs['trigger_msg']
    message = re.sub('^server ', '', message)
    msgsplit = message.split(' ')
    if '-r' in msgsplit:
        message = re.sub(' -r|-r ', '', message)
        raw = True
    else:
        raw = False
    if '-p' in msgsplit:
        message = re.sub(' -p|-p ', '', message)
        showplayer = True
    else:
        showplayer = False
    gather_list = []
    sm = ['j', 'b']
    for x in sm:
        gather_list.append(asyncio.ensure_future(s(kwargs, message, raw, showplayer, x)))
    await asyncio.gather(*gather_list)


async def s(kwargs, message, raw, showplayer, mode):
    sendmsg = await server(message, raw, showplayer, mode)
    sendmsg = await check(sendmsg)
    send = await sendMessage(kwargs, sendmsg)
    await asyncio.sleep(120)
    await revokeMessage(send)


command = {'server': main}
alias = {'s': 'server'}
help = {'server': {
    'help': '~server <服务器地址>:<服务器端口> - 获取Minecraft Java/基岩版服务器motd。'}}
