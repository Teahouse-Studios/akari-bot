import whois


async def check_domain(domain: str):
    return whois.whois(domain)


async def format_domain(msg, info: Dict[str, Any]):
    return f'''\
{info['domain_name']}{f"""
Registrar: {info['registrar']}""" if info['registrar'] is not None else ''}{f"""
Whois Server: {info['whois_server']}""" if info['whois_server'] is not None else ''}{f"""
Referral URL: {info['referral_url']}""" if info['referral_url'] is not None else ''}{f"""
Updated Date: {info['updated_date']}""" if info['updated_date'] is not None else ''}{f"""
Creation Date: {info['creation_date']}""" if info['creation_date'] is not None else ''}'''


