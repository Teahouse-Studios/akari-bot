import re

from core.builtins import Bot
from core.component import module
from .ip import check_ip, format_ip

# from .domain import check_domain, format_domain

w = module('whois', desc='{whois.help.desc}', 
            alias=['ip'],
            developers=['Dianliang233'])


@w.handle('<ip_or_domain>')
async def _(msg: Bot.MessageSession):
    query = msg.parsed_msg['<ip_or_domain>']
    query_type = ip_or_domain(query)
    if query_type == 'ip':
        res = await check_ip(query)
        await msg.finish(await format_ip(msg, res))
    # elif query_type == 'domain':
    #     res = await check_domain(query)
    #     await msg.finish(await format_domain(res))
    else:
        await msg.finish(msg.locale.t("whois.message.unknown"))
        

def ip_or_domain(string: str):
    ip_regex = r'^((\d{1,3}\.){3}\d{1,3})$|^([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$'
    domain_regex = r'^([a-zA-Z0-9-]+\.){1,}[a-zA-Z]{2,}$'
    
    if re.match(ip_regex, string):
        return 'ip'
    elif re.match(domain_regex, string):
        return 'domain'