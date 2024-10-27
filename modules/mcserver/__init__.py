import asyncio
import re

import ipaddress

from core.builtins import Bot
from core.component import module
from core.dirty_check import check
from .server import query_java_server, query_bedrock_server

s = module('mcserver', alias='server', developers=['_LittleC_', 'OasisAkari', 'DoroWolf'], doc=True)


@s.command('<address:port> [-r] [-p] {{server.help}}',
           options_desc={'-r': '{server.help.option.r}', '-p': '{server.help.option.p}'})
async def main(msg: Bot.MessageSession):
    server_address = msg.parsed_msg["<address:port>"]
    raw = msg.parsed_msg.get('-r', False)
    showplayer = msg.parsed_msg.get('-p', False)

    match_object = re.match(r'(.*)[\s:](.*)', server_address, re.M | re.I)
    if match_object:
        server_address = match_object.group(1)

    if check_local_ip(server_address):
        await msg.finish(msg.locale.t('server.message.local_ip'))

    java_info, bedrock_info = await asyncio.gather(
        query_java_server(msg, server_address, raw, showplayer),
        query_bedrock_server(msg, server_address, raw)
    )

    sendmsg = [java_info, bedrock_info]
    if sendmsg:
        sendmsg = '\n'.join(sendmsg)
        sendmsg = await check(sendmsg, msg=msg)
        t = ''.join(x['content'] for x in sendmsg)
        await msg.finish(t)
    else:
        await msg.finish(msg.locale.t('server.message.not_found'))


def check_local_ip(server_address):
    if server_address.lower() == 'localhost':
        return True

    try:
        ip = ipaddress.ip_address(server_address)
        return ip.is_private or ip.is_loopback
    except ValueError:
        return False
