from khl import Bot

from bots.kook.config import KookSecretConfig

token = KookSecretConfig.kook_token

bot = Bot(token=token)
