import asyncio
import re

from core.builtins import Bot
from core.component import module
from core.dirty_check import check
from .server import server

s = module('server', alias='s', developers=['_LittleC_', 'OasisAkari'])


@s.command('<address:port> [-r] [-p] {{server.help}}',
          options_desc={'-r': '{server.help.option.r}', '-p': '{server.help.option.p}'})
async def main(msg: Bot.MessageSession):
    gather_list = []
    match_object = re.match(r'(.*)[\s:](.*)', msg.parsed_msg["<address:port>"], re.M | re.I)
    is_local_ip = False
    server_address = msg.parsed_msg["<address:port>"]
    if match_object:
        server_address = match_object.group(1)

    if server_address == 'localhost':
        is_local_ip = True

    matchserip = re.match(r'(.*?)\.(.*?)\.(.*?)\.(.*?)', server_address)
    if matchserip:
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
    if is_local_ip:
        await msg.finish(msg.locale.t('server.message.error.local_ip'))

    sm = ['j', 'b']
    for x in sm:
        gather_list.append(asyncio.ensure_future(s(
            msg, f'{msg.parsed_msg["<address:port>"]}', msg.parsed_msg.get('-r', False), msg.parsed_msg.get('-p', False
                                                                                                             ), x)))
    g = await asyncio.gather(*gather_list)
    if g == ['', '']:
        message = msg.locale.t('server.message.not_found')
        await msg.finish(message)


async def s(msg: Bot.MessageSession, address, raw, showplayer, mode):
    sendmsg = await server(msg, address, raw, showplayer, mode)
    if sendmsg != '':
        sendmsg = await check(sendmsg)
        for x in sendmsg:
            m = x['content']
            await msg.finish(m)
    return sendmsg
