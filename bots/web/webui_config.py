import os

import orjson as json

from core.constants.path import webui_path
from core.config import Config


def generate_webui_config():
    webui_config_path = os.path.join(webui_path, "config.json")
    if not os.path.exists(webui_config_path):
        with open(webui_config_path, "wb") as f:
            f.write(json.dumps(
                {"enable_https": Config("enable_https", False, table_name="bot_web"),
                 "locale": Config("default_locale", cfg_type=str),
                 "heartbeat_interval": Config("heartbeat_interval", 30, table_name="bot_web"),
                 "heartbeat_timeout": Config("heartbeat_timeout", 5, table_name="bot_web"),
                 "heartbeat_attempt": Config("heartbeat_attempt", 3, table_name="bot_web")
                 },
                option=json.OPT_INDENT_2))
