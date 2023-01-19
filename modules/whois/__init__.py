import ipaddress
from core.utils import get_url
import ujson as json
import socket
from core.builtins.message import MessageSession
from core.component import on_command
from .ip import check_ip, format_ip

w = on_command('whois')


@w.handle('<ip_or_domain>')
async def _(msg: MessageSession):
    query = msg.parsed_msg['<ip_or_domain>']
    query_type = ip_or_domain(query)
    if query_type == 'ip':
        res = await check_ip(query)
        await msg.finish(await format_ip(res))


def ip_or_domain(string: str):
    try:
        ipaddress.ip_address(string)
        return 'ip'
    except ValueError:
        return 'domain'
