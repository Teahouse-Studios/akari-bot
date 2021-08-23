import os
import shutil

from config import Config
from database import BotDBUtil


def init_bot():
    cache_path = os.path.abspath('./cache/')
    if os.path.exists(cache_path):
        shutil.rmtree(cache_path)
        os.mkdir(cache_path)
    else:
        os.mkdir(cache_path)

    base_superuser = Config('base_superuser')
    if base_superuser:
        BotDBUtil.SenderInfo(base_superuser).edit('isSuperUser', True)
