from whois import whois

from config import Config
from core.builtins import Bot
from core.component import module
from core.logger import Logger
from core.utils.text import parse_time_string


def process(input_):
    if isinstance(input_, list):
        input_list = list(set([i.lower() for i in input_]))
        return ', '.join(input_list)
    else:
        return input_


w = module('whois', developers=['DoroWolf'])


@w.handle('<domain> {{whois.help}}')
async def _(msg: Bot.MessageSession, domain: str):
    res = await get_whois(msg, domain)
    await msg.finish(res)


async def get_whois(msg, domain):
    try:
        info = whois(domain)
        Logger.debug(str(info))
    except Exception:
        await msg.finish(msg.locale.t("whois.message.get_failed"))

    domain_name = info.get('domain_name')
    registrar = info.get('registrar')
    whois_server = info.get('whois_server')
    updated_date = info.get('updated_date')
    creation_date = info.get('creation_date')
    expiration_date = info.get('expiration_date')
    name_servers = info.get('name_servers')
    emails = info.get('emails')
    dnssec = info.get('dnssec')
    name = info.get('name')
    org = info.get('org')
    address = info.get('address')
    city = info.get('city')
    state = info.get('state')
    country = info.get('country')
    registrant_postal_code = info.get('registrant_postal_code')

    if not domain_name:
        await msg.finish(msg.locale.t("whois.message.get_failed"))

    if whois_server:
        whois_server = whois_server.lower()

    if updated_date:  # 此时间为UTC时间
        if isinstance(updated_date, list):
            updated_date = updated_date[0]
        updated_date = (updated_date + parse_time_string(Config('timezone_offset', '+8'))).timestamp()

    if creation_date:  # 此时间为UTC时间
        if isinstance(creation_date, list):
            creation_date = creation_date[0]
        creation_date = (creation_date + parse_time_string(Config('timezone_offset', '+8'))).timestamp()

    if expiration_date:  # 此时间为UTC时间
        if isinstance(expiration_date, list):
            expiration_date = expiration_date[0]
        expiration_date = (expiration_date + parse_time_string(Config('timezone_offset', '+8'))).timestamp()

    return f'''\
{msg.locale.t('whois.message.domain_name')}{process(domain_name).lower()}{f"""
{msg.locale.t('whois.message.registrar')}{registrar}""" if registrar else ''}{f"""
{msg.locale.t('whois.message.whois_server')}{whois_server}""" if whois_server else ''}{f"""
{msg.locale.t('whois.message.updated_date')}{msg.ts2strftime(updated_date)}""" if updated_date else ''}{f"""
{msg.locale.t('whois.message.creation_date')}{msg.ts2strftime(creation_date)}""" if creation_date else ''}{f"""
{msg.locale.t('whois.message.expiration_date')}{msg.ts2strftime(expiration_date)}""" if expiration_date else ''}{f"""
{msg.locale.t('whois.message.name_servers')}{process(name_servers)}""" if name_servers else ''}{f"""
{msg.locale.t('whois.message.email')}{process(emails)}""" if emails else ''}{f"""
{msg.locale.t('whois.message.dnssec')}{process(dnssec)}""" if dnssec else ''}{f"""
{msg.locale.t('whois.message.name')}{process(name)}""" if name else ''}{f"""
{msg.locale.t('whois.message.organization')}{process(org)}""" if org else ''}{f"""
{msg.locale.t('whois.message.location')}{f"{process(address)}, " if address else ''}{f"{process(city)}, " if city else ''}{f"{process(state)}, " if state else ''}{process(country)}""" if country else ''}{f"""
{msg.locale.t('whois.message.postal_code')}{process(registrant_postal_code)}""" if registrant_postal_code else ''}'''
