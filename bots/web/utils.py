import os

import orjson as json

from core.constants.path import webui_path


def generate_webui_config(
        enable_https: bool = False,
        default_locale: str = "zh_cn"):
    webui_config_path = os.path.join(webui_path, "config.json")
    if not os.path.exists(webui_config_path):
        with open(webui_config_path, "wb") as f:
            f.write(json.dumps({"enable_https": enable_https,
                                "locale": default_locale
                                }, option=json.OPT_INDENT_2))
