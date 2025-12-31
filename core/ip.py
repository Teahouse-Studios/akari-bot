from core.constants import Secret
from core.logger import Logger
from core.utils.http import get_url


def append_ip(ip_info: dict):
    if ip_info and ip_info.get("ip"):
        Secret.add(ip_info["ip"])
    Secret.ip_address = ip_info.get("ip")
    Secret.ip_country = ip_info.get("country")


async def fetch_ip_info() -> dict:
    try:
        Logger.info("Fetching IP information...")
        ip_info = await get_url("https://api.ip.sb/geoip", timeout=10, fmt="json")
        Logger.success("Successfully fetched IP information.")
        append_ip(ip_info)
        return ip_info
    except Exception:
        Logger.exception("Failed to get IP information.")
        return {}

__all__ = ["fetch_ip_info"]
