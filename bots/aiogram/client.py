from aiogram import Bot, Dispatcher

from config import Config

token = Config('tg_token')

if token:
    bot = Bot(token=token, proxy=Config('proxy'))
    dp = Dispatcher(bot)
else:
    bot = dp = False
