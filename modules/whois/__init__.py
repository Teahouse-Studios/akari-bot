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
    ipv4_regex = r'^(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
    ipv6_regex = r'^(?:(?:(?:(?:[a-fA-F0-9]{1,4}:){6}|::(?:[a-fA-F0-9]{1,4}:){5}|(?:[a-fA-F0-9]{1,4})?::(?:[a-fA-F0-9]{1,4}:){4}|(?:(?:[a-fA-F0-9]{1,4}:)?[a-fA-F0-9]{1,4})?::(?:[a-fA-F0-9]{1,4}:){3}|(?:(?:[a-fA-F0-9]{1,4}:){0,2}[a-fA-F0-9]{1,4})?::(?:[a-fA-F0-9]{1,4}:){2}|(?:(?:[a-fA-F0-9]{1,4}:){0,3}[a-fA-F0-9]{1,4})?::[a-fA-F0-9]{1,4}:|(?:(?:[a-fA-F0-9]{1,4}:){0,4}[a-fA-F0-9]{1,4})?::)(?:[a-fA-F0-9]{1,4}:[a-fA-F0-9]{1,4}|(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)))|::(?:[a-fA-F0-9]{1,4}:){0,5}(?:[a-fA-F0-9]{1,4}:[a-fA-F0-9]{1,4}|(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)))|(?:[a-fA-F0-9]{1,4}:)?(?::[a-fA-F0-9]{1,4}){1,6}(?:\/\d{1,3})?|::(?:ffff(?::0{1,4}){0,1}:){0,1}(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)|(?:(?:[a-fA-F0-9]{1,4}:){1,7}|:)(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?))$'
    domain_regex = r'^([a-zA-Z0-9-]+\.){1,}[a-zA-Z]{2,}$'
    
    if re.match(ipv4_regex, string) or re.match(ipv6_regex, string):
        return 'ip'
    elif re.match(domain_regex, string):
        return 'domain'