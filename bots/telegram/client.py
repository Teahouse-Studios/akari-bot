from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer

from bots.telegram.config import AiogramConfig, AiogramSecretConfig
from core.config.base import CoreSecretConfig

api_url = AiogramConfig.telegram_api_url
token = AiogramSecretConfig.telegram_token
proxy = CoreSecretConfig.proxy

if api_url and proxy:
    session = AiohttpSession(api=TelegramAPIServer.from_base(api_url), proxy=proxy)
elif api_url:
    session = AiohttpSession(api=TelegramAPIServer.from_base(api_url))
elif proxy:
    session = AiohttpSession(proxy=proxy)
else:
    session = None

aiogram_bot = Bot(token=token, session=session)
dp = Dispatcher()
