from khl import Bot

from config import Config

token = Config('kook_token', cfg_type=str)

if token:
    bot = Bot(token=token)
else:
    bot = False
