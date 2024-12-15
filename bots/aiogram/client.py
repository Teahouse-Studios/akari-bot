from aiogram import Bot, Dispatcher

from core.config import Config

token = Config("telegram_token", cfg_type=str, secret=True, table_name="bot_aiogram")

if token:
    bot = Bot(token=token, proxy=Config("proxy", cfg_type=str, secret=True))
    dp = Dispatcher()
else:
    bot = dp = False
