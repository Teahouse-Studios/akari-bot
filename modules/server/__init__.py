import asyncio

from core.dirty_check import check
from core.elements import MessageSession
from core.decorator import on_command
from .server import server


@on_command('server', alias='s', help_doc=('<ServerIP>:<Port> {获取Minecraft Java/基岩版服务器motd。}',
                                           '<ServerIP>:<Port> [-r] {获取Minecraft Java/基岩版服务器motd。（原始信息）}',
                                           '<ServerIP>:<Port> [-p] {获取Minecraft Java/基岩版服务器motd。（包括玩家信息）}'),
            developers=['_LittleC_', 'OasisAkari'],
            allowed_none=False)
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
        send = await msg.sendMessage(
            '发生错误：没有找到任何类型的Minecraft服务器。\n错误汇报地址：https://github.com/Teahouse-Studios/bot/issues/new?assignees=OasisAkari&labels=bug&template=5678.md&title=\n[90秒后撤回消息]')
        await asyncio.sleep(90)
        await send.delete()


async def s(msg: MessageSession, address, raw, showplayer, mode):
    sendmsg = await server(address, raw, showplayer, mode)
    if sendmsg != '':
        sendmsg = await  check(sendmsg)
        sendmsg = '\n'.join(sendmsg)
        send = await msg.sendMessage(sendmsg + '\n[90秒后撤回消息]')
        await asyncio.sleep(90)
        await send.delete()
    return sendmsg
