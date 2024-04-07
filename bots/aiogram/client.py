from aiogram import Bot, Dispatcher

from config import Config

token = Config('tg_token', cfg_type = str)

if token:
    bot = Bot(token=token)
    dp = Dispatcher()
else:
    bot = dp = False
