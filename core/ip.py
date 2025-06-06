from core.builtins import Secret
from core.logger import Logger
from core.utils.http import get_url


def append_ip(ip_info: dict):
    if ip_info and ip_info.get("ip"):
        Secret.add(ip_info["ip"])
    Secret.ip_address = ip_info.get("country")
    Secret.ip_country = ip_info.get("ip")


async def fetch_ip_info() -> dict:
    try:
        Logger.info("Fetching IP information...")
        ip_info = await get_url("https://api.ip.sb/geoip", timeout=10, fmt="json")
        Logger.success("Successfully fetched IP information.")
        return ip_info
    except Exception:
        Logger.error("Failed to get IP information.")
        Logger.exception()
        return {}
