import asyncio
import os
import sys
import uvicorn
from hypercorn.asyncio import serve
from hypercorn.config import Config as Uconfig

sys.path.append(os.getcwd())

from bots.web.info import client_name  # noqa: E402
from bots.web.utils import find_available_port  # noqa: E402
from core.builtins import PrivateAssets  # noqa: E402
from core.config import Config  # noqa: E402
from core.constants.path import assets_path, webui_path  # noqa: E402
from core.logger import Logger  # noqa: E402
from core.terminate import cleanup_sessions  # noqa: E402
from core.utils.info import Info  # noqa: E402

API_PORT = Config("api_port", 5000, table_name="bot_web")
WEBUI_HOST = Config("webui_host", "127.0.0.1", table_name="bot_web")
WEBUI_PORT = Config("webui_port", 8081, table_name="bot_web")

api_port = find_available_port(API_PORT)
webui_port = find_available_port(WEBUI_PORT, host=WEBUI_HOST)

Info.client_name = client_name
PrivateAssets.set(os.path.join(assets_path, "private", "web"))

async def run_fastapi():
    from bots.web.api import app as fastapi_app  # noqa: E402
    Info.client_name = client_name

    if api_port == 0:
        Logger.warning(f"API port is disabled, abort to run.")
        return
    
    ucfg = uvicorn.Config(fastapi_app, port=api_port, log_level="info")
    userver = uvicorn.Server(ucfg)
    await userver.serve()


async def run_flask():
    if os.path.exists(os.path.join(webui_path, "index.html")):
        from bots.web.webui import generate_config, app as flask_app  # noqa: E402
        
        if webui_port == 0:
            Logger.warning(f"WebUI port is disabled, abort to run.")
            return
        
        ucfg = Uconfig()
        ucfg.bind = [f"{WEBUI_HOST}:{webui_port}"]
        if os.path.exists(os.path.join(webui_path, "index.html")):
            generate_config(api_port)
            Logger.info(f"Visit AkariBot WebUI: http://{WEBUI_HOST}:{webui_port}")
            await serve(flask_app, ucfg)


async def main():
    await asyncio.gather(run_flask(), run_fastapi())

if (__name__ == "__main__" or Info.subprocess) and Config("enable", True, table_name="bot_web"):
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(main())
    except (KeyboardInterrupt, SystemExit):
        loop.run_until_complete(cleanup_sessions())