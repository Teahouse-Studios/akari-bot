import asyncio
import os
from contextlib import asynccontextmanager

from argon2 import PasswordHasher
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.wsgi import WSGIMiddleware
from fastapi.responses import RedirectResponse
from flask import Flask, abort, send_from_directory
from slowapi import Limiter
from slowapi.util import get_remote_address
from tortoise import Tortoise

from bots.web.info import *
from core.client.init import client_init
from core.config import Config
from core.constants.path import webui_path
from core.database.models import JobQueuesTable, SenderInfo
from core.logger import Logger
from core.utils.socket import find_available_port, get_local_ip

enable_https = Config("enable_https", default=False, table_name="bot_web")
protocol = "https" if enable_https else "http"

web_host = Config("web_host", "127.0.0.1", table_name="bot_web")
web_port = Config("web_port", 6485, table_name="bot_web")

avaliable_web_port = find_available_port(web_port)

allow_origins = Config("allow_origins", default=[], secret=True, table_name="bot_web")
jwt_secret = Config("jwt_secret", cfg_type=str, secret=True, table_name="bot_web")


def _webui_message():
    if web_host == "0.0.0.0":
        local_ip = get_local_ip()
        network_line = f"Network: {protocol}://{local_ip}:{avaliable_web_port}/webui\n" if local_ip else ""
        message = (
            f"\n---\n"
            f"Visit AkariBot WebUI:\n"
            f"Local:   {protocol}://127.0.0.1:{avaliable_web_port}/webui\n"
            f"{network_line}"
            f"---\n"
        )
    else:
        message = (
            f"\n---\n"
            f"Visit AkariBot WebUI:\n"
            f"{protocol}://{web_host}:{avaliable_web_port}/webui\n"
            f"---\n"
        )

    return message


@asynccontextmanager
async def lifespan(app: FastAPI):
    await client_init(target_prefix_list, sender_prefix_list)
    await SenderInfo.update_or_create(defaults={"superuser": True}, sender_id=f"{sender_prefix}|0")
    if os.path.exists(webui_path):
        Logger.info(_webui_message())
    yield
    await asyncio.sleep(3)  # 等待 server 清理进程
    try:
        await JobQueuesTable.clear_task(time=0)
        await Tortoise.close_connections()
    except Exception:
        pass

app = FastAPI(lifespan=lifespan)
limiter = Limiter(key_func=get_remote_address)
ph = PasswordHasher()

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

if os.path.exists(webui_path):
    flask_app = Flask(__name__)

    @flask_app.route("/")
    @flask_app.route("/<path:path>")
    def serve_webui(path=None):
        if path and "/" in path:
            abort(404)
        return send_from_directory(webui_path, "index.html")

    app.mount("/webui", WSGIMiddleware(flask_app))

    @app.get("/")
    async def redirect_to_webui():
        return RedirectResponse(url="/webui/")

else:
    @app.get("/")
    async def redirect_to_api():
        return RedirectResponse(url="/api")
