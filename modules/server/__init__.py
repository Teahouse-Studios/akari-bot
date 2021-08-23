import asyncio

from core.dirty_check import check
from core.elements import MessageSession
from core.loader.decorator import command
from .server import server


@command('server', alias='s', help_doc=('~server <ServerIP>:<Port> {获取Minecraft Java/基岩版服务器motd。}',
                                        '~server <ServerIP>:<Port> [-r] {获取Minecraft Java/基岩版服务器motd。（原始信息）}',
                                        '~server <ServerIP>:<Port> [-p] {获取Minecraft Java/基岩版服务器motd。（包括玩家信息）}'))
async def main(msg: MessageSession):
    raw = False
    showplayer = False
    if msg.parsed_msg['-r']:
        raw = True
    if msg.parsed_msg['-p']:
        showplayer = True
    gather_list = []
    sm = ['j', 'b']
    for x in sm:
        gather_list.append(asyncio.ensure_future(s(msg, f'{msg.parsed_msg["<ServerIP>:<Port>"]}', raw, showplayer, x)))
    g = await asyncio.gather(*gather_list)
    if g == ['', '']:
        send = await msg.sendMessage('发生错误：没有找到任何类型的Minecraft服务器。\n[90秒后撤回消息]')
        await asyncio.sleep(90)
        await send.delete()


async def s(msg: MessageSession, address, raw, showplayer, mode):
    sendmsg = await server(address, raw, showplayer, mode)
    if sendmsg != '':
        sendmsg = await check(sendmsg)
        send = await msg.sendMessage(sendmsg + '\n[90秒后撤回消息]')
        await asyncio.sleep(90)
        await send.delete()
    return sendmsg
