from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer

from core.config import Config

api_url = Config("telegram_api_url", cfg_type=str, table_name="bot_aiogram")
token = Config("telegram_token", cfg_type=str, secret=True, table_name="bot_aiogram")
proxy = Config("proxy", cfg_type=str, secret=True)

if api_url and proxy:
    session = AiohttpSession(api=TelegramAPIServer.from_base(api_url), proxy=proxy)
elif api_url:
    session = AiohttpSession(api=TelegramAPIServer.from_base(api_url))
elif proxy:
    session = AiohttpSession(proxy=proxy)
else:
    session = None

if token:
    bot = Bot(token=token, session=session)
    dp = Dispatcher()
else:
    bot = dp = None
