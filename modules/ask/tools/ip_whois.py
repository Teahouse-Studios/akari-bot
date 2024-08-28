from modules.ip import check_ip
from .utils import to_json_func, AkariTool


async def ip_whois(ip: str):
    return await to_json_func(check_ip)(ip)


ip_whois_tool = AkariTool.from_function(
    func=ip_whois,
    description='A WHOIS tool for IP addresses. Useful for when you need to answer questions about IPv4/v6 addresses. ONLY INVOKE THIS WHEN YOU WANT INFO ABOUT IP ADDRESS, otherwise, use search.'
)
