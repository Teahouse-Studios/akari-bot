from aiogram import Bot, Dispatcher

from config import Config

token = Config('tg_token')

bot = Bot(token=token)
if bot and token:
    dp = Dispatcher(bot)
else:
    dp = False
