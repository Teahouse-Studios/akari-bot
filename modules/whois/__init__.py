from whois import whois

from core.builtins import Bot, Plain, Image
from core.component import module
from core.utils.image import msgchain2image


def process(input):
    if isinstance(input, list) and len(input) > 0:
        return input[0]
    else:
        return input


def get_value(dict, key):
    if key in dict:
        return dict[key]
    else:
        return None


w = module('whois', developers=['DoroWolf'])


@w.handle('<domain> {{whois.help}}')
async def _(msg: Bot.MessageSession, domain: str):
    res = await get_whois(msg, domain)
    output = await msg.finish(res)

    img = await msgchain2image([Plain(output)], msg)
    await msg.finish([Image(img)])


async def get_whois(msg, domain):
    try:
        info = whois(domain)
    except BaseException:
        await msg.finish(msg.locale.t("whois.message.get_failed"))

    domain_name = get_value(info, 'domain_name')
    registrar = get_value(info, 'registrar')
    whois_server = get_value(info, 'whois_server')
    updated_date = get_value(info, 'updated_date')
    creation_date = get_value(info, 'creation_date')
    expiration_date = get_value(info, 'expiration_date')
    name_servers = get_value(info, 'name_servers')
    dnssec = get_value(info, 'dnssec')
    name = get_value(info, 'name')
    org = get_value(info, 'org')
    address = get_value(info, 'address')
    city = get_value(info, 'city')
    state = get_value(info, 'state')
    country = get_value(info, 'country')
    registrant_postal_code = get_value(info, 'registrant_postal_code')

    if not domain_name:
        await msg.finish(msg.locale.t("whois.message.get_failed"))

    if whois_server:
        whois_server = whois_server.lower()

    if name_servers:
        name_servers_list = list(set([i.lower() for i in name_servers]))
    else:
        name_servers_list = []

    return f'''\
{msg.locale.t('whois.message.domain_name')}{process(domain_name).lower()}{f"""
{msg.locale.t('whois.message.registrar')}{registrar}""" if registrar else ''}{f"""
{msg.locale.t('whois.message.whois_server')}{whois_server}""" if whois_server else ''}{f"""
{msg.locale.t('whois.message.updated_date')}{str(process(updated_date))}""" if updated_date else ''}{f"""
{msg.locale.t('whois.message.creation_date')}{str(process(creation_date))}""" if creation_date else ''}{f"""
{msg.locale.t('whois.message.expiration_date')}{str(process(expiration_date))}""" if expiration_date else ''}{f"""
{msg.locale.t('whois.message.name_servers')}{', '.join(name_servers_list)}""" if name_servers else ''}{f"""
{msg.locale.t('whois.message.dnssec')}{process(dnssec)}""" if dnssec else ''}{f"""
{msg.locale.t('whois.message.name')}{process(name)}""" if name else ''}{f"""
{msg.locale.t('whois.message.organization')}{process(org)}""" if org else ''}{f"""
{msg.locale.t('whois.message.location')}{f"{process(address)}, " if address else ''}{f"{process(city)}, " if city else ''}{f"{process(state)}, " if state else ''}{process(country)}""" if country else ''}{f"""
{msg.locale.t('whois.message.postal_code')}{process(registrant_postal_code)}""" if registrant_postal_code else ''}'''
