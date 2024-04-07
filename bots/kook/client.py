from khl import Bot

from config import Config

token = Config('kook_token', '')

if token:
    bot = Bot(token=token)
else:
    bot = False
