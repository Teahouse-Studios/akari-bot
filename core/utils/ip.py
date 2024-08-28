import traceback

from core.logger import Logger
from core.types import Secret
from core.utils.http import get_url


class IP:
    address = None
    country = None


def append_ip(ip_info):
    Secret.add(ip_info['ip'])
    IP.country = ip_info['country']
    IP.address = ip_info['ip']


async def fetch_ip_info() -> dict:
    try:
        Logger.info('Fetching IP information...')
        ip_info = await get_url('https://api.ip.sb/geoip', timeout=10, fmt='json')
        Logger.info('Successfully fetched IP information.')
        return ip_info
    except Exception:
        Logger.error('Failed to get IP information.')
        Logger.error(traceback.format_exc())
