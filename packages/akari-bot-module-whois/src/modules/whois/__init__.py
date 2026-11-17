from datetime import UTC

from whois import whois

from core.builtins.bot import Bot
from core.builtins.message.internal import I18NContext, Plain
from core.component import module
from core.logger import Logger


def format_lst(input_):
    if isinstance(input_, list):
        input_list = list({i.lower() for i in input_})
        return ", ".join(input_list)
    return input_


w = module("whois", developers=["DoroWolf"], doc=True)


@w.command("<domain> {{I18N:whois.help}}")
async def _(msg: Bot.MessageSession, domain: str):
    res = await get_whois(msg, domain)
    await msg.finish(res)


async def get_whois(msg: Bot.MessageSession, domain: str):
    try:
        info = whois(domain)
        Logger.debug(str(info))

        domain_name = info.get("domain_name")
        registrar = info.get("registrar")
        whois_server = info.get("whois_server")
        updated_date = info.get("updated_date")
        creation_date = info.get("creation_date")
        expiration_date = info.get("expiration_date")
        name_servers = info.get("name_servers")
        emails = info.get("emails")
        dnssec = info.get("dnssec")
        name = info.get("name")
        org = info.get("org")
        address = info.get("address")
        city = info.get("city")
        state = info.get("state")
        country = info.get("country")
        registrant_postal_code = info.get("registrant_postal_code")

        if not domain_name:
            await msg.finish(I18NContext("whois.message.get_failed"))

        if whois_server:
            whois_server = whois_server.lower()

        if updated_date:  # 此时间为UTC时间
            if isinstance(updated_date, list):
                updated_date = updated_date[0]
            updated_date = updated_date.replace(tzinfo=UTC)

        if creation_date:  # 此时间为UTC时间
            if isinstance(creation_date, list):
                creation_date = creation_date[0]
            creation_date = creation_date.replace(tzinfo=UTC)

        if expiration_date:  # 此时间为UTC时间
            if isinstance(expiration_date, list):
                expiration_date = expiration_date[0]
            expiration_date = expiration_date.replace(tzinfo=UTC)

        res = []

        domain_name_label = str(I18NContext("whois.message.domain_name"))
        res.append(f"{domain_name_label}{format_lst(domain_name).lower()}")
        if registrar:
            registrar_label = str(I18NContext("whois.message.registrar"))
            res.append(Plain(f"{registrar_label}{registrar}"))

        if whois_server:
            whois_server_label = str(I18NContext("whois.message.whois_server"))
            res.append(Plain(f"{whois_server_label}{whois_server}"))

        if updated_date:
            updated_date_label = str(I18NContext("whois.message.updated_date"))
            res.append(Plain(f"{updated_date_label}{msg.format_time(updated_date.timestamp())}"))

        if creation_date:
            creation_date_label = str(I18NContext("whois.message.creation_date"))
            res.append(Plain(f"{creation_date_label}{msg.format_time(creation_date.timestamp())}"))

        if expiration_date:
            expiration_date_label = str(I18NContext("whois.message.expiration_date"))
            res.append(Plain(f"{expiration_date_label}{msg.format_time(expiration_date.timestamp())}"))

        if name_servers:
            name_servers_label = str(I18NContext("whois.message.name_servers"))
            res.append(Plain(f"{name_servers_label}{format_lst(name_servers)}"))

        if emails:
            emails_label = str(I18NContext("whois.message.email"))
            res.append(Plain(f"{emails_label}{format_lst(emails)}"))

        if dnssec:
            dnssec_label = str(I18NContext("whois.message.dnssec"))
            res.append(Plain(f"{dnssec_label}{format_lst(dnssec)}"))

        if name:
            name_label = str(I18NContext("whois.message.name"))
            res.append(Plain(f"{name_label}{format_lst(name)}"))

        if org:
            org_label = str(I18NContext("whois.message.organization"))
            res.append(Plain(f"{org_label}{format_lst(org)}"))

        location_parts = []
        if address:
            location_parts.append(format_lst(address))
        if city:
            location_parts.append(format_lst(city))
        if state:
            location_parts.append(format_lst(state))
        if country:
            location_parts.append(format_lst(country))

        if location_parts:
            location_str = ", ".join(location_parts)
            location_label = str(I18NContext("whois.message.location"))
            res.append(Plain(f"{location_label}{location_str}"))

        if registrant_postal_code:
            postal_code_label = str(I18NContext("whois.message.postal_code"))
            res.append(Plain(f"{postal_code_label}{format_lst(registrant_postal_code)}"))

        return res
    except Exception:
        await msg.finish(I18NContext("whois.message.get_failed"))
