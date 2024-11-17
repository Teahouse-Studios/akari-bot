from khl import Bot

from core.config import config

token = config('kook_token', cfg_type=str, secret=True)

if token:
    bot = Bot(token=token)
else:
    bot = False
