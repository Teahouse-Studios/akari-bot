from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer

from bots.telegram.config import AiogramConfig, AiogramSecretConfig
from core.config.network import proxy, ssl_verify

api_url = AiogramConfig.telegram_api_url
token = AiogramSecretConfig.telegram_token
TELEGRAM_CONNECTION_LIMIT = 16

session_kwargs = {"limit": TELEGRAM_CONNECTION_LIMIT}
if api_url:
    session_kwargs["api"] = TelegramAPIServer.from_base(api_url)
if proxy:
    session_kwargs["proxy"] = proxy
session = AiohttpSession(**session_kwargs)
if not ssl_verify:
    # aiogram 未提供关闭证书校验的参数，只能改写它在建连时使用的连接器配置。
    session._connector_init["ssl"] = False

aiogram_bot = Bot(token=token, session=session)
dp = Dispatcher()
