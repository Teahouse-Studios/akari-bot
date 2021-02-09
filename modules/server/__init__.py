import asyncio
import re

from core.template import sendMessage, revokeMessage
from .server import server


async def main(kwargs: dict):
    message = kwargs['trigger_msg']
    message = re.sub('^server ', '', message)
    msgsplit = message.split(' ')
    if '-r' in msgsplit:
        message = re.sub(' -r|-r ', '', message)
        sendmsg = await server(message, raw=True)
    else:
        sendmsg = await server(message)
    send = await sendMessage(kwargs, sendmsg)
    await asyncio.sleep(30)
    await revokeMessage(send)


command = {'server': main}
help = {'server': {
    'help': '~server <服务器地址>:<服务器端口> - 获取Minecraft Java/基岩版服务器motd。'}}
