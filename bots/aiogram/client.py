from aiogram import Bot, Dispatcher

from core.config import config

token = config('telegram_token', cfg_type=str, secret=True)

if token:
    bot = Bot(token=token, proxy=config('proxy', cfg_type=str, secret=True))
    dp = Dispatcher()
else:
    bot = dp = False
