import os

import urllib3
from nio import AsyncClient, AsyncClientConfig

from config import Config
from core.logger import Logger

homeserver: str = Config('matrix_homeserver')
user: str = Config('matrix_user')
token: str = Config('matrix_token')

store_path = os.path.abspath('./matrix_store')
if not os.path.exists(store_path):
    os.mkdir(store_path)

store_path_nio = os.path.join(store_path, 'nio')
if not os.path.exists(store_path_nio):
    os.mkdir(store_path_nio)

store_path_next_batch = os.path.join(store_path, 'next_batch.txt')

if homeserver and user and token:
    if homeserver.endswith('/'):
        Logger.warn(f"The matrix_homeserver ends with a slash(/), and this may cause M_UNRECOGNIZED error")
    homeserver_host = urllib3.util.parse_url(homeserver).host
    bot: AsyncClient = AsyncClient(homeserver,
                                   user,
                                   device_id='AkariBot',
                                   store_path=store_path_nio,
                                   config=AsyncClientConfig(store_sync_tokens=True))
    bot.access_token = token
else:
    bot = False
