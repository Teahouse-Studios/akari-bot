import datetime
from whois import whois

from core.builtins import Bot, Plain, Image
from core.component import module
from core.utils.image import msgchain2image


def process(input):
        if isinstance(input, list) and len(input) > 0:
            return input[0]
        else:
            return input


w = module('whois', desc='{whois.help.desc}',
           developers=['DoroWolf'])


@w.handle('<domain>')
async def _(msg: Bot.MessageSession, domain: str):
    res = await get_whois(msg, domain)
    output = await msg.finish(res)
    
    img = await msgchain2image([Plain(output)])
    await msg.finish([Image(img)])


async def get_whois(msg, domain):
    try:
        info = whois(domain)
    except:
        await msg.finish("whois.message.error.get_failed")

    
    if info['name_servers']:
        name_servers = [ns for ns in info['name_servers'] if ns.islower()]
    else:
        name_servers = None

    return f'''\
{msg.locale.t('whois.message.domain_name')}{info['domain_name'][1]}{f"""
{msg.locale.t('whois.message.registrar')}{info['registrar']}""" if info['registrar'] else ''}{f"""
{msg.locale.t('whois.message.whois_server')}{info['whois_server']}""" if info['whois_server'] else ''}{f"""
{msg.locale.t('whois.message.updated_date')}{str(process(info['updated_date']))}""" if info['updated_date'] else ''}{f"""
{msg.locale.t('whois.message.creation_date')}{str(process(info['creation_date']))}""" if info['creation_date'] else ''}{f"""
{msg.locale.t('whois.message.expiration_date')}{str(process(info['expiration_date']))}""" if info['expiration_date'] else ''}{f"""
{msg.locale.t('whois.message.name_servers')}{', '.join(name_servers)}""" if info['name_servers'] else ''}{f"""
{msg.locale.t('whois.message.dnssec')}{info['dnssec']}""" if info['dnssec'] else ''}{f"""
{msg.locale.t('whois.message.name')}{process(info['name'])}""" if info['name'] else ''}{f"""
{msg.locale.t('whois.message.organization')}{process(info['org'])}""" if info['org'] else ''}{f"""
{msg.locale.t('ip.message.location')}{f"{process(info['address'])}, " if info['address'] else ''}{f"{process({info['city'])}, " if info['city'] else ''}{f"{{process(info['state'])}, " if info['state'] else ''}{{process(info['country'])}""" if info['country'] else ''}{f"""
{msg.locale.t('whois.message.postal_code')}{process(info['registrant_postal_code'])}""" if info['registrant_postal_code'] else ''}'''
