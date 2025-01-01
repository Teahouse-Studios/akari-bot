from fastapi import WebSocket
from datetime import datetime
import glob
import os
import psutil
import platform
import re
import sys
import time
import uuid
from cpuinfo import get_cpu_info
from datetime import datetime, timedelta, UTC

import asyncio
import jwt
import uvicorn
from argon2 import PasswordHasher
from fastapi import FastAPI, Request, HTTPException, Depends, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles

from bots.api.info import client_name
from core.constants import config_filename, config_path, logs_path
from core.queue import JobQueue
from core.scheduler import Scheduler
from core.utils.info import Info

sys.path.append(os.getcwd())

from core.bot_init import init_async  # noqa: E402
from core.builtins import PrivateAssets  # noqa: E402
from core.config import Config  # noqa: E402
from core.constants.path import assets_path  # noqa: E402
from core.database import BotDBUtil  # noqa: E402
from core.extra.scheduler import load_extra_schedulers  # noqa: E402
from core.loader import ModulesManager  # noqa: E402
from core.logger import Logger  # noqa: E402
from core.utils.i18n import Locale  # noqa: E402
from modules.wiki.utils.dbutils import WikiTargetInfo  # noqa: E402

started_time = datetime.now()
PrivateAssets.set(os.path.join(assets_path, "private", "api"))
ACCESS_TOKEN = Config("api_access_token", cfg_type=str, secret=True, table_name="bot_api")
ALLOW_ORIGINS = Config("api_allow_origins", default=['*'], cfg_type=(str, list), secret=True, table_name="bot_api")
JWT_SECRET = Config("jwt_secret", cfg_type=str, secret=True, table_name="bot_api")
PASSWORD_PATH = os.path.join(PrivateAssets.path, ".password")
MAX_LOG_HISTORY = 1000

last_file_line_count = {}
logs_history = []


def verify_access_token(request: Request):
    if request.url.path == "/favicon.ico":
        return
    if not ACCESS_TOKEN:
        return

    auth_header = request.headers.get("Authorization")
    if not auth_header or auth_header != f"Bearer {ACCESS_TOKEN}":
        raise HTTPException(status_code=403, detail="forbidden")


# app = FastAPI(dependencies=[Depends(verify_access_token)])
app = FastAPI()
ph = PasswordHasher()


app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.mount("/assets", StaticFiles(directory="assets"), name="assets")


@app.on_event("startup")
async def startup_event():
    await init_async(start_scheduler=False)
    load_extra_schedulers()
    Scheduler.start()
    await JobQueue.secret_append_ip()
    await JobQueue.web_render_status()


@app.get("/favicon.ico", response_class=FileResponse)
async def favicon():
    favicon_path = os.path.join(assets_path, "favicon.ico")
    return FileResponse(favicon_path)


@app.get("/")
async def main():
    return {"message": "Hello AkariBot!"}


@app.post("/auth")
async def auth(request: Request):
    try:
        if not os.path.exists(PASSWORD_PATH):
            return {"message": "success"}

        body = await request.json()
        password = body["password"]
        remember = body.get("remember", False)

        with open(PASSWORD_PATH, "r") as file:
            stored_password = file.read().strip()

        try:
            ph.verify(stored_password, password)  # 验证输入的密码是否与存储的哈希匹配
        except Exception:
            raise HTTPException(status_code=401, detail="invalid password")

        payload = {
            "device_id": str(uuid.uuid4()),
            "exp": datetime.now(UTC) + (timedelta(days=365) if remember else timedelta(hours=24)),  # 过期时间
            "iat": datetime.now(UTC),  # 签发时间
            "iss": "auth-api"  # 签发者
        }
        jwt_token = jwt.encode(payload, JWT_SECRET, algorithm='HS256')

        return {"message": "success", "deviceToken": jwt_token}

    except HTTPException as e:
        raise e
    except Exception as e:
        Logger.error(str(e))
        raise HTTPException(status_code=400, detail="bad request")


@app.post("/verify-token")
async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer())):
    try:
        token = credentials.credentials
        payload = jwt.decode(token, JWT_SECRET, algorithm='HS256')
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="invalid token")


@app.post("/change-password")
async def change_password(request: Request):
    try:
        body = await request.json()
        new_password = body.get("new_password", "")
        password = body.get("password", "")

        # 读取旧密码
        if not os.path.exists(PASSWORD_PATH):
            if new_password == "":
                raise HTTPException(status_code=400, detail="new password required")
            new_password_hashed = ph.hash(new_password)
            with open(PASSWORD_PATH, "w") as file:
                file.write(new_password_hashed)
            return {"message": "success"}

        with open(PASSWORD_PATH, "r") as file:
            stored_password = file.read().strip()

        try:
            ph.verify(stored_password, password)
        except Exception:
            raise HTTPException(status_code=401, detail="invalid password")

        # 设置新密码
        new_password_hashed = ph.hash(new_password)
        with open(PASSWORD_PATH, "w") as file:
            file.write(new_password_hashed)

        return {"message": "success"}
    except HTTPException as e:
        raise e
    except Exception as e:
        Logger.error(str(e))
        raise HTTPException(status_code=400, detail="bad request")


@app.get("/server-info")
async def server_info():
    return {
        "message": "success",
        "os": {
            "system": platform.system(),
            "version": platform.version(),
            "machine": platform.machine(),
            "boot_time": psutil.boot_time(),
        },
        "bot": {
            "running_time": (datetime.now() - started_time).total_seconds(),
            "python_version": platform.python_version(),
            "version": Info.version,
            "web_render_local_status": Info.web_render_local_status,
            "web_render_status": Info.web_render_status,
        },
        "cpu": {
            "cpu_brand": get_cpu_info()["brand_raw"],
            "cpu_percent": psutil.cpu_percent(interval=1),  # 获取 CPU 使用率
        },
        "memory": {
            "total": psutil.virtual_memory().total / (1024 * 1024),  # 总内存
            "used": psutil.virtual_memory().used / (1024 * 1024),  # 已用内存
            "percent": psutil.virtual_memory().percent,  # 内存使用百分比
        },
        "disk": {
            "total": psutil.disk_usage('/').total / (1024 * 1024 * 1024),  # 磁盘总容量
            "used": psutil.disk_usage('/').used / (1024 * 1024 * 1024),  # 磁盘已使用容量
            "percent": psutil.disk_usage('/').percent,  # 磁盘使用百分比
        }
    }


@app.get("/config")
async def get_config_list():
    try:
        files = os.listdir(config_path)
        cfg_files = [f for f in files if f.endswith(".toml")]

        if config_filename in cfg_files:
            cfg_files.remove(config_filename)
            cfg_files.insert(0, config_filename)

        return {"message": "success", "cfg_files": cfg_files}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="not found")
    except Exception as e:
        Logger.error(str(e))
        raise HTTPException(status_code=400, detail="bad request")


@app.get("/config/{cfg_filename}")
async def get_config_file(cfg_filename: str):
    if not os.path.exists(config_path):
        raise HTTPException(status_code=404, detail="not found")
    if not cfg_filename.endswith(".toml"):
        raise HTTPException(status_code=400, detail="bad request")
    cfg_file_path = os.path.normpath(os.path.join(config_path, cfg_filename))
    if not cfg_file_path.startswith(config_path):
        raise HTTPException(status_code=400, detail="bad request")

    try:
        with open(cfg_file_path, 'r', encoding='UTF-8') as f:
            content = f.read()
        return {"message": "success", "content": content}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="not found")
    except Exception as e:
        Logger.error(str(e))
        raise HTTPException(status_code=400, detail="bad request")


@app.post("/config/{cfg_filename}")
async def edit_config_file(cfg_filename: str, request: Request):
    if not os.path.exists(config_path):
        raise HTTPException(status_code=404, detail="not found")
    if not cfg_filename.endswith(".toml"):
        raise HTTPException(status_code=400, detail="bad request")
    cfg_file_path = os.path.normpath(os.path.join(config_path, cfg_filename))
    if not cfg_file_path.startswith(config_path):
        raise HTTPException(status_code=400, detail="bad request")
    try:
        body = await request.json()
        content = body["content"]
        with open(cfg_file_path, 'w', encoding='UTF-8') as f:
            f.write(content)
        return {"message": "success"}

    except Exception as e:
        Logger.error(str(e))
        raise HTTPException(status_code=400, detail="bad request")


@app.get("/target/{target_id}")
async def get_target(target_id: str):
    target = BotDBUtil.TargetInfo(target_id)
    if not target.query:
        return HTTPException(status_code=404, detail="not found")
    enabled_modules = target.enabled_modules
    is_muted = target.is_muted
    custom_admins = target.custom_admins
    locale = target.locale
    options = target.get_option()

    wiki_target = WikiTargetInfo(target_id)
    wiki_headers = wiki_target.get_headers()
    wiki_start_wiki = wiki_target.get_start_wiki()
    wiki_interwikis = wiki_target.get_interwikis()

    return {
        "targetId": target_id,
        "enabledModules": enabled_modules,
        "isMuted": is_muted,
        "customAdmins": custom_admins,
        "locale": locale,
        "options": options,
        "wiki": {
            "headers": wiki_headers,
            "startWiki": wiki_start_wiki,
            "interwikis": wiki_interwikis,
        },
    }


@app.get("/sender/{sender_id}")
async def get_sender(sender_id: str):
    sender = BotDBUtil.SenderInfo(sender_id)
    if not sender.query:
        return HTTPException(status_code=404, detail="not found")

    return {
        "senderId": sender_id,
        "isInBlockList": sender.is_in_block_list,
        "isInAllowList": sender.is_in_allow_list,
        "isSuperUser": sender.is_super_user,
        "warns": sender.warns,
        "disableTyping": sender.disable_typing,
        "petal": sender.petal,
    }


@app.get("/modules")
async def get_module_list():
    return {"modules": ModulesManager.return_modules_list()}


@app.get("/modules/{target_id}")
async def get_target_modules(target_id: str):
    target_data = BotDBUtil.TargetInfo(target_id)
    if not target_data.query:
        return HTTPException(status_code=404, detail="not found")
    target_from = "|".join(target_id.split("|")[:-2])
    modules = ModulesManager.return_modules_list(target_from=target_from)
    enabled_modules = target_data.enabled_modules
    return {
        "targetId": target_id,
        "modules": {k: v for k, v in modules.items() if k in enabled_modules},
    }


@app.post("/modules/{target_id}/enable")
async def enable_modules(target_id: str, request: Request):
    try:
        target_data = BotDBUtil.TargetInfo(target_id)
        if not target_data.query:
            return HTTPException(status_code=404, detail="not found")
        target_from = "|".join(target_id.split("|")[:-2])

        body = await request.json()
        modules = body["modules"]
        modules = modules if isinstance(modules, list) else [modules]
        modules = [
            m
            for m in modules
            if m in ModulesManager.return_modules_list(target_from=target_from)
        ]
        target_data.enable(modules)
        return {"message": "success"}
    except HTTPException as e:
        raise e
    except Exception as e:
        Logger.error(str(e))
        return HTTPException(status_code=400, detail="bad request")


@app.post("/modules/{target_id}/disable")
async def disable_modules(target_id: str, request: Request):
    try:
        target_data = BotDBUtil.TargetInfo(target_id)
        if not target_data.query:
            return HTTPException(status_code=404, detail="not found")
        target_from = "|".join(target_id.split("|")[:-2])

        body = await request.json()
        modules = body["modules"]
        modules = modules if isinstance(modules, list) else [modules]
        modules = [
            m
            for m in modules
            if m in ModulesManager.return_modules_list(target_from=target_from)
        ]
        target_data.disable(modules)
        return {"message": "success"}
    except HTTPException as e:
        raise e
    except Exception as e:
        Logger.error(str(e))
        return HTTPException(status_code=400, detail="bad request")


@app.get("/locale/{locale}/{string}")
async def get_locale(locale: str, string: str):
    try:
        return {
            "locale": locale,
            "string": string,
            "translation": Locale(locale).t(string, False),
        }
    except TypeError:
        return HTTPException(status_code=404, detail="not found")


@app.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket):
    global logs_history
    await websocket.accept()

    if logs_history:
        await websocket.send_text("\n".join(logs_history))

    while True:
        today_logs = glob.glob(f"{logs_path}/*_{datetime.today().strftime('%Y-%m-%d')}.log")
        today_logs = [log for log in today_logs if 'console' not in os.path.basename(log)]

        if today_logs:
            for log_file in today_logs:
                try:
                    current_line_count = 0
                    new_lines = []

                    with open(log_file, 'r', encoding='utf-8') as f:
                        for i, line in enumerate(f):
                            if i >= last_file_line_count.get(log_file, 0):
                                if line:
                                    new_lines.append(line[:-1])  # 移除行尾换行符
                            current_line_count = i + 1  # 文件的总行数

                    if new_lines:
                        await websocket.send_text("\n".join(new_lines))
                        logs_history.extend(new_lines)

                        logs_history.sort(key=lambda line: extract_timestamp(line) or datetime.min)

                        while len(logs_history) > MAX_LOG_HISTORY:
                            logs_history.pop(0)

                        while logs_history and not is_log_line_valid(logs_history[0]):
                            logs_history.pop(0)

                    last_file_line_count[log_file] = current_line_count

                except Exception:
                    continue

        await asyncio.sleep(0.1)


def is_log_line_valid(line: str) -> bool:
    log_pattern = r'^\[.+\]\[[a-zA-Z0-9\._]+:[a-zA-Z0-9\._]+:\d+\]\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\]\[[A-Z]+\]:'
    return bool(re.match(log_pattern, line))


def extract_timestamp(log_line: str):
    log_time_pattern = r'\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]'
    match = re.search(log_time_pattern, log_line)
    if match:
        return datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S")
    return None


if (__name__ == "__main__" or Info.subprocess) and Config(
    "enable", True, table_name="bot_api"
):
    while True:
        Info.client_name = client_name
        uvicorn.run(
            app, port=Config("api_port", 5000, table_name="bot_api"), log_level="info"
        )
        Logger.error("API Server crashed, is the port occupied?")
        Logger.error("Retrying in 5 seconds...")
        time.sleep(5)
