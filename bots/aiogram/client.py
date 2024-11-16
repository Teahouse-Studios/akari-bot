from aiogram import Bot, Dispatcher

from core.config import Config
from core.utils.http import proxy

token = Config('telegram_token', cfg_type=str)

if token:
    bot = Bot(token=token, proxy=Config('proxy', cfg_type=str))
    dp = Dispatcher()
else:
    bot = dp = False
