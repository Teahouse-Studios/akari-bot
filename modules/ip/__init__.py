import ipaddress
import socket
from typing import Any, Dict

from core.builtins.bot import Bot
from core.builtins.message.internal import I18NContext, Plain
from core.component import module
from core.logger import Logger
from core.utils.http import get_url

ip = module("ip", developers=["Dianliang233"], doc=True)


@ip.command("<ip_address> {{I18N:ip.help}}")
async def _(msg: Bot.MessageSession, ip_address: str):
    try:
        ip = ipaddress.ip_address(ip_address)
        if isinstance(ip, ipaddress.IPv6Address) and "::" in ip_address:
            ip_address = ip.exploded
    except Exception:
        await msg.finish(I18NContext("ip.message.invalid"))
    res = await check_ip(ip_address)
    await msg.finish(await format_ip(msg, res), disable_secret_check=True)


async def check_ip(ip: str):
    info = ipaddress.ip_address(ip)
    ip_property = ""
    real_ip = None
    skip_geoip = False
    if info.is_multicast:
        ip_property = "multicast"
    elif info.is_global:
        ip_property = "global"
    elif info.is_loopback:
        ip_property = "loopback"
        skip_geoip = True
    elif info.is_unspecified:
        ip_property = "unspecified"
        skip_geoip = True
    elif info.is_link_local:
        ip_property = "link_local"
        skip_geoip = True
    elif info.is_reserved:
        ip_property = "reserved"
        skip_geoip = True
    elif info.is_private:
        ip_property = "private"
        skip_geoip = True
    elif isinstance(info, ipaddress.IPv6Address):
        if info.is_site_local:
            ip_property = "site_local"
        elif info.ipv4_mapped:
            ip_property = "ipv4_mapped"
            real_ip = info.ipv4_mapped.compressed
        elif info.sixtofour:
            ip_property = "sixtofour"
            real_ip = info.sixtofour.compressed
        elif info.teredo:
            ip_property = "teredo"
            ip = str(info.teredo)
    else:
        ip_property = "unknown"
        skip_geoip = True

    res = {
        "ip": ip,
        "version": info.version,
        "country_code": None,
        "country": None,
        "region_code": None,
        "region": None,
        "city": None,
        "postal_code": None,
        "contient_code": None,
        "latitude": None,
        "longitude": None,
        "organization": None,
        "asn": None,
        "asn_organization": None,
        "offset": None,
        "reverse": None,
        "ip_property": ip_property,
        "real_ip": real_ip
    }
    if not skip_geoip:
        data = await get_url(f"https://api.ip.sb/geoip/{ip}", 200, fmt="json")
        for key in res:
            if key in data:
                res[key] = data[key]
        try:
            reverse = socket.getnameinfo((ip, 0), 0)
            res["reverse"] = reverse[0]
        except Exception:
            Logger.warning("Unable to fetch reverse DNS.")

    return res


def zzzq(msg: Bot.MessageSession, country: str):
    if msg.session_info.client_name in ["KOOK", "QQ", "QQBot"] and \
            country in ["Hong Kong", "Macao", "Taiwan"]:
        return "China"
    return country


def parse_coordinate(axis: str, value: float):
    if axis == "latitude":
        return f"{abs(value)}°{"N" if value > 0 else "S"}"
    if axis == "longitude":
        return f"{abs(value)}°{"E" if value > 0 else "W"}"


async def format_ip(msg: Bot.MessageSession, info: Dict[str, Any]):
    ip_property_map = {
        "global": I18NContext("ip.message.ip_property.global"),
        "private": I18NContext("ip.message.ip_property.private"),
        "reserved": I18NContext("ip.message.ip_property.reserved"),
        "multicast": I18NContext("ip.message.ip_property.multicast"),
        "link_local": I18NContext("ip.message.ip_property.link_local"),
        "loopback": I18NContext("ip.message.ip_property.loopback"),
        "unspecified": I18NContext("ip.message.ip_property.unspecified"),
        "ipv4_mapped": I18NContext("ip.message.ip_property.ipv4_mapped"),
        "sixtofour": I18NContext("ip.message.ip_property.sixtofour"),
        "teredo": I18NContext("ip.message.ip_property.teredo"),
        "site_local": I18NContext("ip.message.ip_property.site_local"),
        "unknown": I18NContext("message.unknown"),
    }

    res = []

    res.append(Plain(info["ip"]))

    ip_type_label = str(I18NContext("ip.message.type"))
    ip_property_label = str(ip_property_map.get(info.get("ip_property"), ip_property_map["unknown"]))
    ip_property_suffix = str(I18NContext("ip.message.ip_property"))
    ip_type = f"IPv{info["version"]}{ip_property_label}{ip_property_suffix}"
    res.append(Plain(f"{ip_type_label}{ip_type}"))

    real_ip = info.get("real_ip")
    if real_ip:
        real_ip_label = str(I18NContext("ip.message.real_ip"))
        res.append(Plain(f"{real_ip_label}{real_ip}"))

    location_parts = []
    for key in ("city", "region", "country"):
        value = info.get(key)
        if value:
            if key == "country":
                value = zzzq(msg, value)
            location_parts.append(value)
    location = ", ".join(location_parts)

    longitude = info.get("longitude")
    latitude = info.get("latitude")
    if longitude and latitude:
        longitude = parse_coordinate("longitude", longitude)
        latitude = parse_coordinate("latitude", latitude)
        location += f" ({longitude}, {latitude})"

    location_label = str(I18NContext("ip.message.location"))
    res.append(Plain(f"{location_label}{location}"))

    postal_code = info.get("postal_code")
    if postal_code:
        postal_code_label = str(I18NContext("ip.message.postal_code"))
        res.append(Plain(f"{postal_code_label}{postal_code}"))

    organization = info.get("organization")
    if organization:
        organization_label = str(I18NContext("ip.message.organization"))
        res.append(Plain(f"{organization_label}{organization}"))

    asn = info.get("asn")
    if asn:
        asn_label = str(I18NContext("ip.message.asn"))
        asn_org = info.get("asn_organization")
        asn_org = f" ({asn_org})" if asn_org else ""
        res.append(Plain(f"{asn_label}{asn}{asn_org}"))

    offset = info.get("offset")
    if offset:
        utc_label = str(I18NContext("ip.message.utc"))
        offset_hours = offset / 3600
        res.append(Plain(f"{utc_label}UTC{offset_hours:+g}"))

    reverse = info.get("reverse")
    ip = info.get("ip")
    if reverse and reverse != ip:
        reverse_label = str(I18NContext("ip.message.reverse"))
        res.append(Plain(f"{reverse_label}{reverse}"))

    return res
