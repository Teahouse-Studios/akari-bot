from typing import Any
import json
import socket
import ipaddress
from core.utils import get_url
import os

iso = json.load(open(os.path.dirname(os.path.abspath(
    __file__)) + '/iso.json', 'r', encoding='utf-8'))


async def check_ip(ip: str):
    info = ipaddress.ip_address(ip)
    ip_property = ''
    real_ip = None
    skip_geoip = False
    if info.is_multicast:
        ip_property = 'multicast'
    elif info.is_global:
        ip_property = 'global'
    elif info.is_loopback:
        ip_property = 'loopback'
        skip_geoip = True
    elif info.is_unspecified:
        ip_property = 'unspecified'
        skip_geoip = True
    elif info.is_link_local:
        ip_property = 'link_local'
        skip_geoip = True
    elif info.is_reserved:
        ip_property = 'reserved'
        skip_geoip = True
    elif isinstance(info, ipaddress.IPv6Address):
        if info.is_site_local:
            ip_property = 'site_local'
        elif info.ipv4_mapped:
            ip_property = 'ipv4_mapped'
            real_ip = info.ipv4_mapped.compressed
        elif info.sixtofour:
            ip_property = 'sixtofour'
            real_ip = info.sixtofour.compressed
        elif info.teredo:
            ip_property = 'teredo'
            ip = str(info.teredo)
    elif info.is_private:
        ip_property = 'private'

    res = {
        'ip': ip,
        'version': info.version,
        'country_code': None,
        'country': None,
        'region_code': None,
        'region': None,
        'city': None,
        'postal_code': None,
        'contient_code': None,
        'latitude': None,
        'longitude': None,
        'organization': None,
        'asn': None,
        'asn_organization': None,
        'offset': None,
        'reverse': None,
        'ip_property': ip_property,
        'real_ip': real_ip
    }
    if not skip_geoip:
        data = json.loads(await get_url('https://api.ip.sb/geoip/' + ip))
        reverse = socket.getnameinfo((ip, 0), 0)
        print(reverse)
        print(reverse[0])
        res['reverse'] = reverse[0]
        for key in res:
            if key in data:
                res[key] = data[key]
    return res


def parse_coordinate(axis: str, value: float):
    if axis == 'latitude':
        return f'{value}°{"N" if value > 0 else "S"}'
    elif axis == 'longitude':
        return f'{value}°{"E" if value > 0 else "W"}'


async def format_ip(info: dict[str, Any]):
    ip_property = {
        'global': '全局',
        'private': '私有',
        'reserved': '保留',
        'multicast': '多播',
        'link_local': '链路本地',
        'loopback': '回环',
        'unspecified': '未指定',
        'ipv4_mapped': 'IPv4 映射',
        'sixtofour': '6to4 ',
        'teredo': 'Teredo ',
        'site_local': '站点本地'
    }

    return f'''\
{info['ip']}
类型：IPv{info['version']} {ip_property[info['ip_property']]}地址{f"""
实际 IP：{info['real_ip']}""" if info['real_ip'] is not None else ''}{f"""
位置：{iso[info['country_code']]}""" if info['country_code'] is not None else ''}{info['region'] if info['region'] is not None else ''}{info['city'] if info['city'] is not None else ''}{f"（{parse_coordinate('longitude', info['longitude'])}, {parse_coordinate('latitude', info['latitude'])}）" if info['longitude'] is not None and info['latitude'] is not None else ''}{f"""
邮编：{info['postal_code']}""" if info['postal_code'] is not None else ''}{f"""
组织：{info['organization']}""" if info['organization'] is not None else ''}{f"""
ASN：{info['asn']}""" if info['asn'] is not None else ''}{f"（{info['asn_organization']}）" if info['asn_organization'] is not None else ''}{f"""
时区：UTC{(info['offset'] / 3600):+g}""" if info['offset'] is not None else ''}{f"""
反向解析：{info['reverse']}""" if info['reverse'] is not None and info['reverse'] != info['ip'] else ''}'''
