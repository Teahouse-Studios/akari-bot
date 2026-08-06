import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from argon2 import PasswordHasher
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from slowapi import Limiter

from bots.web.info import *
from core.client.init import client_init
from core.config import CFGManager
from bots.web.config import WebConfig, WebSecretConfig
from core.constants.path import assets_path, webui_path
from core.database.models import SenderUnionInfo
from core.logger import Logger
from core.utils.random import Random
from core.utils.socket import find_available_port, get_local_ip

if (webui_path / "dist").exists():
    dist_path: Path = webui_path / "dist"
else:
    try:
        from akari_bot_webui.entrypoint import dist_path
    except ImportError:
        dist_path = Path()


enable_https = WebConfig.enable_https
protocol = "https" if enable_https else "http"

web_host = WebConfig.web_host
web_port = WebConfig.web_port

available_web_port = find_available_port(web_port)

allow_origins = WebSecretConfig.allow_origins

# 反向代理下 request.client 记录的是代理自身的地址，真实地址由 uvicorn 的
# ProxyHeadersMiddleware 依 forwarded_allow_ips 判定来源可信后，从 X-Forwarded-For 解析并回填。
forwarded_allow_ips = WebSecretConfig.forwarded_allow_ips

# 无法判定来源的请求统一归入该标识。不回退为 127.0.0.1，以免被误当作本机的受信任访问。
UNKNOWN_CLIENT_IP = "unknown"


def get_client_ip(request: Request) -> str:
    """
    取请求方地址，用于限流、封禁与访问记录。

    :param request: 当前请求。
    :return: 请求方地址；ASGI 传输未提供来源信息时返回 ``unknown``。
    """
    if request.client and request.client.host:
        return request.client.host
    return UNKNOWN_CLIENT_IP


jwt_secret = WebSecretConfig.jwt_secret
if not jwt_secret:
    # jwt_secret 须在 web 子进程首次启动时随机生成并持久化，属只读进程中的合法写入
    CFGManager.edit_write("jwt_secret", Random.randbytes(32).hex(), secret=True, table_name="bot_web")
    jwt_secret = WebSecretConfig.jwt_secret


def _webui_message():
    if web_host == "0.0.0.0":  # skipcq
        local_ip = get_local_ip()
        network_line = f"Network: {protocol}://{local_ip}:{available_web_port}/webui\n" if local_ip else ""
        message = (
            f"\n---\n"
            f"Visit AkariBot WebUI:\n"
            f"Local:   {protocol}://127.0.0.1:{available_web_port}/webui\n"
            f"{network_line}"
            f"---\n"
        )
    else:
        message = f"\n---\nVisit AkariBot WebUI:\n{protocol}://{web_host}:{available_web_port}/webui\n---\n"

    return message


@asynccontextmanager
async def lifespan(app: FastAPI):
    await client_init(target_prefix_list, sender_prefix_list)
    sender_union_info = await SenderUnionInfo.resolve_union(f"{sender_prefix}|0")
    await sender_union_info.edit_attr("superuser", True)
    if dist_path.exists():
        Logger.info(_webui_message())
    yield
    await asyncio.Event().wait()  # 等待 server 清理进程


app = FastAPI(lifespan=lifespan)
limiter = Limiter(key_func=get_client_ip)
ph = PasswordHasher()

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


if dist_path.exists():

    @app.get("/webui/{path:path}")
    async def serve_webui(path: str):
        file_path = (dist_path / path).resolve()

        try:
            file_path.relative_to(dist_path)
        except ValueError:
            return FileResponse(dist_path / "index.html")
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)

        return FileResponse(dist_path / "index.html")

    @app.get("/")
    @app.get("/webui")
    async def redirect_to_webui():
        return RedirectResponse(url="/webui/")
else:

    @app.get("/")
    async def redirect_to_api():
        return RedirectResponse(url="/api")


@app.get("/favicon.ico")
async def favicon():
    return FileResponse(assets_path / "favicon.ico")
