import asyncio
import re

from core.template import sendMessage, revokeMessage
from core.dirty_check import check
from .server import server


async def main(kwargs: dict):
    message = kwargs['trigger_msg']
    message = re.sub('^server ', '', message)
    msgsplit = message.split(' ')
    if '-r' in msgsplit:
        message = re.sub(' -r|-r ', '', message)
        raw = True
    else:
        raw =False
    if '-p' in msgsplit:
        message = re.sub(' -p|-p ', '', message)
        showplayer = True
    else:
        showplayer = False
    sendmsg = server(message, raw, showplayer)
    sendmsg = await check([sendmsg])
    send = await sendMessage(kwargs, sendmsg)
    await asyncio.sleep(30)
    await revokeMessage(send)


command = {'server': main}
help = {'server': {
    'help': '~server <服务器地址>:<服务器端口> - 获取Minecraft Java/基岩版服务器motd。'}}
