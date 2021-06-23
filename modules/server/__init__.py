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
        msgsplit.remove('-r')
        raw = True
    else:
        raw = False
    if '-p' in msgsplit:
        msgsplit.remove('-p')
        showplayer = True
    else:
        showplayer = False
    message = ' '.join(msgsplit)
    gather_list = []
    sm = ['j', 'b']
    for x in sm:
        gather_list.append(asyncio.ensure_future(s(kwargs, message, raw, showplayer, x)))
    g = await asyncio.gather(*gather_list)
    if g == ['', '']:
        send = await sendMessage(kwargs, '发生错误：没有找到任何类型的Minecraft服务器。')
        await asyncio.sleep(90)
        await revokeMessage(send)


async def s(kwargs, message, raw, showplayer, mode):
    sendmsg = await server(message, raw, showplayer, mode)
    if sendmsg != '':
        sendmsg = await check(sendmsg)
        send = await sendMessage(kwargs, sendmsg + '\n[90秒后撤回消息]')
        await asyncio.sleep(90)
        await revokeMessage(send)
    return sendmsg


command = {'server': main}
alias = {'s': 'server'}
help = {'server': {
    'help': '~server <服务器地址>:<服务器端口> - 获取Minecraft Java/基岩版服务器motd。'}}
