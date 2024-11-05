from khl import Bot

from core.config import Config

token = Config('kook_token', cfg_type=str)

if token:
    bot = Bot(token=token)
else:
    bot = False
