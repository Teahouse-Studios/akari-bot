from milky import AsyncMilkyClient

from bots.milky.config import MilkyConfig, MilkySecretConfig


def normalize_base_url(host: str) -> str:
    host = host.strip().rstrip("/")
    if not host.startswith(("http://", "https://")):
        host = f"http://{host}"
    return host


access_token = MilkySecretConfig.qq_access_token
qq_host = MilkyConfig.qq_host

milky_bot = AsyncMilkyClient(normalize_base_url(qq_host), access_token=access_token)
