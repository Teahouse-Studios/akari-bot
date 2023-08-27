from aiogram import Bot, Dispatcher

from config import Config

token = Config('tg_token')
client_name = 'Telegram'


if token:
    bot = Bot(token=token)
    dp = Dispatcher(bot)
else:
    bot = dp = False
