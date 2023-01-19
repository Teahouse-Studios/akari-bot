from typing import Any, Union
import json
import socket
import ipaddress
from core.utils import get_url
import os
import whois

iso = json.load(open(os.path.dirname(os.path.abspath(
    __file__)) + './iso.json', 'r', encoding='utf-8'))


async def check_domain(domain: str):
    return whois.whois(domain)


async def format_domain(info: whois.WhoisEntry):
    res = ''
    for key, value in info.items():
        res += f'\n{key}：{value}'
    return res
