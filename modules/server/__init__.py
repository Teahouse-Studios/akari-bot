import asyncio

from core.component import on_command, on_option
from core.dirty_check import check
from core.elements import MessageSession
from database import BotDBUtil
from .server import server


on_option('server_disable_revoke', desc='关闭server命令的自动撤回')  # 临时解决方案，后续会改动，归属到toggle命令下

s = on_command('server', alias='s', developers=['_LittleC_', 'OasisAkari'])


@s.handle(['<ServerIP>:<Port> {获取Minecraft Java/基岩版服务器motd。}',
           '<ServerIP>:<Port> [-r] {获取Minecraft Java/基岩版服务器motd。（原始信息）}',
           '<ServerIP>:<Port> [-p] {获取Minecraft Java/基岩版服务器motd。（包括玩家信息）}'])
async def main(msg: MessageSession):
    enabled_addon = BotDBUtil.Module(msg).check_target_enabled_module('server_disable_revoke')
    gather_list = []
    sm = ['j', 'b']
    for x in sm:
        gather_list.append(asyncio.ensure_future(s(
            msg, f'{msg.parsed_msg["<ServerIP>:<Port>"]}', msg.parsed_msg['-r'], msg.parsed_msg['-p'], x, enabled_addon)))
    g = await asyncio.gather(*gather_list)
    if g == ['', '']:
        msg_ = '发生错误：没有找到任何类型的Minecraft服务器。' \
              '\n错误汇报地址：https://github.com/Teahouse-Studios/bot/issues/new?assignees=OasisAkari&labels=bug&template=report_bug.yaml&title=%5BBUG%5D%3A+'
        if msg.Feature.delete and not enabled_addon:
            msg_ += '[90秒后撤回消息]'
        send = await msg.sendMessage(msg_)
        if msg.Feature.delete and not enabled_addon:
            await msg.sleep(90)
            await send.delete()


async def s(msg: MessageSession, address, raw, showplayer, mode, enabled_addon):
    sendmsg = await server(address, raw, showplayer, mode)
    if sendmsg != '':
        sendmsg = await check(sendmsg)
        for x in sendmsg:
            m = x['content']
            if msg.Feature.delete and not enabled_addon:
                m += '\n[90秒后撤回消息]'
            send = await msg.sendMessage(m)
            if msg.Feature.delete and not enabled_addon:
                await msg.sleep(90)
                await send.delete()
    return sendmsg
