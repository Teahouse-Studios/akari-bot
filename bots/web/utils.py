import os
import socket

import orjson as json

from core.constants.path import webui_path


def generate_webui_config(port: int,
                          host: str = "127.0.0.1",
                          enable_https: bool = False,
                          default_locale: str = "zh_cn"):
    webui_config_path = os.path.join(webui_path, "config.json")
    if not os.path.exists(webui_config_path):
        protocol = "https" if enable_https else "http"
        with open(webui_config_path, "wb") as f:
            f.write(json.dumps(
                {"api_url": f"{protocol}://{host}:{port}",
                    "enable_https": enable_https,
                    "locale": default_locale}
            ))


def check_port_available(port: int, host: str = "0.0.0.0") -> bool:
    try:
        socket.gethostbyname(host)

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            result = sock.connect_ex((host, port))
            return result != 0
    except socket.gaierror:
        return False


def find_available_port(start_port: int, max_retries: int = 100, host: str = "127.0.0.1") -> int:
    for offset in range(max_retries):
        current_port = start_port + offset
        if current_port <= 0:
            break
        if check_port_available(current_port, host):
            return current_port
    return 0
