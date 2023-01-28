import ipaddress

from core.builtins.message import MessageSession
from core.component import on_command
from .ip import check_ip, format_ip

# from .domain import check_domain, format_domain

w = on_command('whois', desc='查询 IP Whois 信息',
               developers=['Dianliang233'])


@w.handle('<ip_or_domain>')
async def _(msg: MessageSession):
    query = msg.parsed_msg['<ip_or_domain>']
    query_type = ip_or_domain(query)
    if query_type == 'ip':
        res = await check_ip(query)
        await msg.finish(await format_ip(res))
    # elif query_type == 'domain':
    #     res = await check_domain(query)
    #     await msg.finish(await format_domain(res))


def ip_or_domain(string: str):
    try:
        ipaddress.ip_address(string)
        return 'ip'
    except ValueError:
        return 'domain'
