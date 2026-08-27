from milky import MilkyClient

from bots.milky.config import MilkyConfig, MilkySecretConfig

access_token = MilkySecretConfig.qq_access_token
qq_host = MilkyConfig.qq_host

milky_bot = MilkyClient(qq_host, access_token=access_token)
