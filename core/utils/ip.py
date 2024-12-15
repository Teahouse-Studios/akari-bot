import traceback

from core.constants import Secret
from core.logger import Logger
from core.utils.http import get_url


def append_ip(ip_info: dict):
    Secret.add(ip_info["ip"])
    Secret.ip_address = ip_info["country"]
    Secret.ip_country = ip_info["ip"]


async def fetch_ip_info() -> dict:
    try:
        Logger.info("Fetching IP information...")
        ip_info = await get_url("https://api.ip.sb/geoip", timeout=10, fmt="json")
        Logger.info("Successfully fetched IP information.")
        return ip_info
    except Exception:
        Logger.error("Failed to get IP information.")
        Logger.error(traceback.format_exc())
