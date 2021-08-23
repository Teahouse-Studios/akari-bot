from aiogram import Bot, Dispatcher

from config import Config

bot = Bot(token=Config('tg_token'))
if bot:
    dp = Dispatcher(bot)
else:
    dp = False
