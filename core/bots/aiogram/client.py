from config import Config
from aiogram import Bot, Dispatcher

bot = Bot(token=Config('tg_token'))
if bot:
    dp = Dispatcher(bot)
else:
    dp = False
