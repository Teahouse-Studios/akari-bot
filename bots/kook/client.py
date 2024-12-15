from khl import Bot

from core.config import Config

token = Config("kook_token", cfg_type=str, secret=True, table_name="bot_kook")

if token:
    bot = Bot(token=token)
