from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer

from bots.telegram.config import AiogramConfig, AiogramSecretConfig
from core.config.base import CoreSecretConfig

api_url = AiogramConfig.telegram_api_url
token = AiogramSecretConfig.telegram_token
proxy = CoreSecretConfig.proxy
TELEGRAM_CONNECTION_LIMIT = 16

session_kwargs = {"limit": TELEGRAM_CONNECTION_LIMIT}
if api_url:
    session_kwargs["api"] = TelegramAPIServer.from_base(api_url)
if proxy:
    session_kwargs["proxy"] = proxy
session = AiohttpSession(**session_kwargs)

aiogram_bot = Bot(token=token, session=session)
dp = Dispatcher()
