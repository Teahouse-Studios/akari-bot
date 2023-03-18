import json
import os

import whois


async def check_domain(domain: str):
    return whois.whois(domain)


async def format_domain(info: whois.WhoisEntry):
    res = ''
    for key, value in info.items():
        res += f'\n{key}：{value}'
    return res
