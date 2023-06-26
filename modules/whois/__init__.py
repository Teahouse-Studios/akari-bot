import whois
from core.builtins import Bot, Plain, Image
from core.component import module
from core.utils.image import msgchain2image


w = module('whois', desc='{whois.help.desc}',
           developers=['DoroWolf'])


@w.handle('<domain>')
async def _(msg: Bot.MessageSession, domain: str):
    res = await get_whois(msg, domain)
    output = await msg.finish(res)
    
    img = await msgchain2image([Plain(output)])
    await msg.finish([BImage(img)])

async def get_whois(msg, domain):
    try:
        info = whois.whois(domain)
    except whois.parser.PywhoisError as e:
        await msg.finish("whois.message.error.get_failed")

    name_servers = [ns for ns in data['name_servers'] if ns.islower()]

    return f'''\
{msg.locale.t('whois.message.domain_name')}{data['domain_name'][1]}{f"""
{msg.locale.t('whois.message.registrar')}{info['registrar']}""" if info['registrar'] is not None else ''}{f"""
{msg.locale.t('whois.message.whois_server')}{{info['whois_server']}""" if info['whois_server'] is not None else ''}{f"""
{msg.locale.t('whois.message.updated_date')}{str(info['updated_date'])}""" if info['updated_date'] is not None else ''}{f"""
{msg.locale.t('whois.message.creation_date')}{str(info['creation_date'][0])}""" if info['creation_date'] is not None else ''}{f"""
{msg.locale.t('whois.message.expiration_date')}{str(info['expiration_date'][0])}""" if info['expiration_date'] is not None else ''}{f"""
{msg.locale.t('whois.message.name_servers')}{', '.join(name_servers)}""" if info['name_servers'] is not None else ''}{f"""
{msg.locale.t('whois.message.dnssec')}{info['dnssec']}""" if info['dnssec'] is not None else ''}{f"""
{msg.locale.t('whois.message.name')}{info['name']}""" if info['name'] is not None else ''}{f"""
{msg.locale.t('whois.message.organization')}{info['org']}""" if info['org'] is not None else ''}{f"""
{msg.locale.t('ip.message.location')}{f"{info['address']}, " if info['address'] is not None else ''}{f"{info['city']}, " if info['city'] is not None else ''}{f"{info['state']}, " if info['state'] is not None else ''}{info['country']}""" if info['country'] is not None else ''}{f"""
{msg.locale.t('whois.message.postal_code')}{info['registrant_postal_code']}""" if info['registrant_postal_code'] is not None else ''}'''