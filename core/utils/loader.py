import os

from core.constants import modules_path, Info
from core.logger import Logger

import orjson as json


def fetch_modules_list() -> list:
    """
    获取模块列表。
    :return: 模块列表
    """
    if not Info.binary_mode:
        dir_list = os.listdir(modules_path)
    else:
        try:
            Logger.warning(
                "Binary mode detected, trying to load pre-built modules list..."
            )
            js = "assets/modules_list.json"
            with open(js, "r", encoding="utf-8") as f:
                dir_list = json.loads(f.read())
        except Exception:
            Logger.error("Failed to load pre-built modules list, using default list.")
            dir_list = os.listdir(modules_path)
    return dir_list
