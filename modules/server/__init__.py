import asyncio
import re
import traceback

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
    matchObj = re.match(r'(.*)[\s:](.*)', msg.parsed_msg["<ServerIP:Port>"], re.M | re.I)
    is_local_ip = False
    server_address = msg.parsed_msg["<ServerIP:Port>"]
    if matchObj:
        server_address = matchObj.group(1)
    if server_address == 'localhost':
        is_local_ip = True
    matchserip = re.match(r'(.*?)\.(.*?)\.(.*?)\.(.*?)', server_address)
    if matchserip:
        try:
            if matchserip.group(1) == '192':
                if matchserip.group(2) == '168':
                    is_local_ip = True
            if matchserip.group(1) == '172':
                if 16 <= int(matchserip.group(2)) <= 31:
                    is_local_ip = True
            if matchserip.group(1) == '10':
                if 0 <= int(matchserip.group(2)) <= 255:
                    is_local_ip = True
            if matchserip.group(1) == '127':
                is_local_ip = True
            if matchserip.group(1) == '0':
                if matchserip.group(2) == '0':
                    if matchserip.group(3) == '0':
                        is_local_ip = True
        except:
            traceback.print_exc()
    if is_local_ip:
        return await msg.sendMessage('发生错误：IP地址无效。')
    sm = ['j', 'b']
    for x in sm:
        gather_list.append(asyncio.ensure_future(s(
            msg, f'{msg.parsed_msg["<ServerIP:Port>"]}', msg.parsed_msg.get('-r', False), msg.parsed_msg.get('-p', False
                                                                                                             ), x,
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
