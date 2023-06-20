from modules.whois.ip import check_ip
from .utils import to_json_func, AkariTool

ip_whois_tool = AkariTool(
    name='IpWhois',
    func=to_json_func(check_ip),
    description='A WHOIS tool for IP addresses. Useful for when you need to answer questions about IP addresses. Input should be a valid IP address. Output is a JSON document.'
)
