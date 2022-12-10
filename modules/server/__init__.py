import asyncio

from core.builtins.message import MessageSession
from core.component import on_command
from core.dirty_check import check
from .server import server

s = on_command('server', alias='s', developers=['_LittleC_', 'OasisAkari'])


@s.handle('<ServerIP:Port> [-r] [-p] {获取Minecraft Java/基岩版服务器motd。}',
          options_desc={'-r': '显示原始信息', '-p': '显示玩家列表'})
async def main(msg: MessageSession):
    enabled_addon = msg.options.get('server_revoke')
    if enabled_addon is None:
        enabled_addon = True
    gather_list = []
    sm = ['j', 'b']
    for x in sm:
        gather_list.append(asyncio.ensure_future(s(
            msg, f'{msg.parsed_msg["<ServerIP:Port>"]}', msg.parsed_msg.get('-r', False), msg.parsed_msg.get('-p', False), x,
            enabled_addon)))
    g = await asyncio.gather(*gather_list)
    if g == ['', '']:
        msg_ = '发生错误：没有找到任何类型的Minecraft服务器。'
        if msg.Feature.delete and enabled_addon:
            msg_ += '[90秒后撤回消息]'
        send = await msg.sendMessage(msg_)
        if msg.Feature.delete and enabled_addon:
            await msg.sleep(90)
            await send.delete()
            await msg.finish()


@s.handle('revoke <enable|disable> {是否启用自动撤回功能（默认为是）。}')
async def revoke(msg: MessageSession):
    if msg.parsed_msg.get('<enable|disable>') == 'enable':
        msg.data.edit_option('server_revoke', True)
        await msg.finish('已启用自动撤回功能。')
    elif msg.parsed_msg.get('<enable|disable>') == 'disable':
        msg.data.edit_option('server_revoke', False)
        await msg.finish('已禁用自动撤回功能。')


async def s(msg: MessageSession, address, raw, showplayer, mode, enabled_addon):
    sendmsg = await server(address, raw, showplayer, mode)
    if sendmsg != '':
        sendmsg = await check(sendmsg)
        for x in sendmsg:
            m = x['content']
            if msg.Feature.delete and enabled_addon:
                m += '\n[90秒后撤回消息]'
            send = await msg.sendMessage(m)
            if msg.Feature.delete and enabled_addon:
                await msg.sleep(90)
                await send.delete()
                await msg.finish()
    return sendmsg
