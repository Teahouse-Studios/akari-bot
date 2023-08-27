from khl import Bot

from config import Config

token = Config('kook_token')
client_name = 'Kook'

if token:
    bot = Bot(token=token)
else:
    bot = False
