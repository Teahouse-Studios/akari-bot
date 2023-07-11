from nio import AsyncClient

from config import Config
from core.logger import Logger

homeserver: str = Config('matrix_homeserver')
user: str = Config('matrix_user')
token: str = Config('matrix_token')


if homeserver and user and token:
    if homeserver.endswith('/'):
        Logger.warn(f"The matrix_homeserver ends with a slash(/), and this may cause M_UNRECOGNIZED error")
    bot: AsyncClient = AsyncClient(homeserver, user, device_id="AkariBot")
    bot.access_token = token
else:
    bot = False
