import os
import sys
import time
from multiprocessing import Process
import uvicorn

sys.path.append(os.getcwd())

from bots.web.info import client_name  # noqa: E402
from core.builtins import PrivateAssets  # noqa: E402
from core.config import Config  # noqa: E402
from core.constants.path import assets_path, webui_path  # noqa: E402
from core.logger import Logger  # noqa: E402
from core.utils.info import Info  # noqa: E402

API_PORT = Config("api_port", 5000, table_name="bot_web")
WEBUI_PORT = Config("webui_port", 8081, table_name="bot_web")

Info.client_name = client_name
PrivateAssets.set(os.path.join(assets_path, "private", "web"))


def run_fastapi():
    while True:
        from bots.web.api import app as fastapi_app  # noqa: E402
        Info.client_name = client_name
        uvicorn.run(fastapi_app, port=API_PORT, log_level="info")
        Logger.error("API Server crashed, is the port occupied?")
        Logger.error("Retrying in 5 seconds...")
        time.sleep(5)


def run_flask():
    from bots.web.webui import generate_config, app as flask_app  # noqa: E402
    if os.path.exists(os.path.join(webui_path, "index.html")):
        generate_config()
        Logger.info(f"Visit AkariBot WebUI: http://127.0.0.1:{WEBUI_PORT}")
        flask_app.run(port=WEBUI_PORT)
        Logger.error("WebUI crashed, is the port occupied?")
        Logger.error("Please check and restart WebUI manually.")


if (__name__ == "__main__" or Info.subprocess) and Config("enable", True, table_name="bot_web"):
    p1 = Process(target=run_fastapi)
    p2 = Process(target=run_flask)
    p1.start()
    p2.start()
