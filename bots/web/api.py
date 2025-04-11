import asyncio
import glob
import os
import platform
import re
import secrets
import sys
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, UTC

import jwt
import orjson as json
import psutil
import uvicorn
from argon2 import PasswordHasher
from cpuinfo import get_cpu_info
from fastapi import FastAPI, WebSocket
from fastapi import Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter
from slowapi.util import get_remote_address
from tortoise.exceptions import DoesNotExist

sys.path.append(os.getcwd())

from bots.web.bot import API_PORT, WEBUI_HOST, WEBUI_PORT  # noqa: E402
from bots.web.info import client_name  # noqa: E402
from core.bot_init import init_async  # noqa: E402
from core.builtins import PrivateAssets  # noqa: E402
from core.close import cleanup_sessions  # noqa: E402
from core.config import Config  # noqa: E402
from core.constants import config_filename, config_path, logs_path  # noqa: E402
from core.constants.path import assets_path  # noqa: E402
from core.database.models import SenderInfo, TargetInfo  # noqa: E402
from core.extra.scheduler import load_extra_schedulers  # noqa: E402
from core.i18n import Locale  # noqa: E402
from core.loader import ModulesManager  # noqa: E402
from core.logger import Logger  # noqa: E402
from core.queue import JobQueue  # noqa: E402
from core.scheduler import Scheduler  # noqa: E402
from core.utils.info import Info  # noqa: E402

started_time = datetime.now()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_async(start_scheduler=False)
    load_extra_schedulers()
    Scheduler.start()
    await JobQueue.secret_append_ip()
    await JobQueue.web_render_status()
    yield
    await cleanup_sessions()

app = FastAPI(lifespan=lifespan)
limiter = Limiter(key_func=get_remote_address)
ph = PasswordHasher()

ALLOW_ORIGINS = Config("api_allow_origins", default=[], secret=True, table_name="bot_web")
JWT_SECRET = Config("jwt_secret", cfg_type=str, secret=True, table_name="bot_web")
CSRF_TOKEN_PATH = os.path.join(PrivateAssets.path, ".CSRF_token")
PASSWORD_PATH = os.path.join(PrivateAssets.path, ".password")
CSRF_TOKEN_EXPIRY = 3600
MAX_LOG_HISTORY = 1000

ALLOW_ORIGINS.append(f"http://{WEBUI_HOST}:{WEBUI_PORT}")

last_file_line_count = {}
logs_history = []

if not os.path.exists(CSRF_TOKEN_PATH):
    with open(CSRF_TOKEN_PATH, "wb") as f:
        f.write(json.dumps([]))


def load_csrf_tokens():
    with open(CSRF_TOKEN_PATH, "r") as f:
        return json.loads(f.read())


def save_csrf_tokens(tokens):
    with open(CSRF_TOKEN_PATH, "wb") as f:
        f.write(json.dumps(tokens))


def verify_csrf_token(request: Request):
    csrf_token = request.headers.get("X-XSRF-TOKEN")
    device_token = request.cookies.get("deviceToken")
    if not csrf_token:
        raise HTTPException(status_code=403, detail="Missing CSRF token")

    token_entries = load_csrf_tokens()

    for token_entry in token_entries:
        stored_token = token_entry.get("csrf_token")
        stored_device_token = token_entry.get("device_token")
        stored_timestamp = token_entry.get("token_timestamp")

        if stored_token == csrf_token and stored_device_token == device_token:
            if time.time() - stored_timestamp > CSRF_TOKEN_EXPIRY:
                raise HTTPException(status_code=403, detail="CSRF token expired")
            return {"message": "Success"}

    raise HTTPException(status_code=403, detail="Invalid CSRF token")


def verify_jwt(request: Request):
    auth_token = request.cookies.get("deviceToken")
    if not auth_token:
        raise HTTPException(status_code=401, detail="Invalid request")

    try:
        payload = jwt.decode(auth_token, JWT_SECRET, algorithms=["HS256"])
        if payload.get("iat") > datetime.now(UTC).timestamp():
            raise HTTPException(status_code=400, detail="Invalid token")
        return {"message": "Success", "payload": payload}

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid token")


app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.mount("/assets", StaticFiles(directory="assets"), name="assets")


@app.get("/")
async def redirect_root():
    return RedirectResponse(url="/api")


@app.get("/favicon.ico", response_class=FileResponse)
@limiter.limit("2/second")
async def _(request: Request):
    favicon_path = os.path.join(assets_path, "favicon.ico")
    return FileResponse(favicon_path)


@app.get("/api/")
@limiter.limit("2/second")
async def favicon(request: Request):
    return {"message": "Hello, AkariBot!"}


@app.get("/api/verify-token")
@limiter.limit("2/second")
async def verify_token(request: Request):
    verify_jwt(request)


@app.get("/api/get-csrf-token")
@limiter.limit("2/second")
async def set_csrf_token(request: Request):
    verify_jwt(request)
    csrf_token = secrets.token_hex(32)
    device_token = request.cookies.get("deviceToken")
    current_time = time.time()

    token_entries = load_csrf_tokens()
    token_entries = [
        token for token in token_entries if current_time - token["token_timestamp"] < CSRF_TOKEN_EXPIRY
    ]
    token_entries.append({
        "csrf_token": csrf_token,
        "device_token": device_token,
        "token_timestamp": current_time
    })
    save_csrf_tokens(token_entries)

    return {"message": "Success", "csrf_token": csrf_token}


@app.post("/api/auth")
@limiter.limit("10/minute")
async def auth(request: Request, response: Response):
    try:
        payload = {
            "device_id": str(uuid.uuid4()),
            "exp": datetime.now(UTC) + timedelta(hours=24),  # 过期时间
            "iat": datetime.now(UTC),  # 签发时间
            "iss": "auth-api"  # 签发者
        }
        jwt_token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")

        if not os.path.exists(PASSWORD_PATH):
            response.set_cookie(
                key="deviceToken",
                value=jwt_token,
                httponly=True,
                secure=True,
                samesite="none",
                expires=datetime.now(UTC) + timedelta(hours=24)
            )
            return {"message": "Success"}

        body = await request.json()
        password = body.get("password", "")
        remember = body.get("remember", False)

        with open(PASSWORD_PATH, "r") as file:
            stored_password = file.read().strip()

        try:
            ph.verify(stored_password, password)
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid password")

        payload = {
            "device_id": str(uuid.uuid4()),
            "exp": datetime.now(UTC) + (timedelta(days=365) if remember else timedelta(hours=24)),
            "iat": datetime.now(UTC),
            "iss": "auth-api"
        }
        jwt_token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")

        response.set_cookie(
            key="deviceToken",
            value=jwt_token,
            httponly=True,
            secure=True,
            samesite="none",
            expires=datetime.now(UTC) + (timedelta(days=365) if remember else timedelta(hours=24))
        )

        return {"message": "Success"}

    except HTTPException as e:
        raise e
    except Exception as e:
        Logger.error(str(e))
        raise HTTPException(status_code=400, detail="Bad request")


@app.post("/api/change-password")
@limiter.limit("10/minute")
async def change_password(request: Request):
    try:
        verify_jwt(request)
        verify_csrf_token(request)
        body = await request.json()
        new_password = body.get("new_password", "")
        password = body.get("password", "")

        # 读取旧密码
        if not os.path.exists(PASSWORD_PATH):
            if new_password == "":
                raise HTTPException(status_code=400, detail="New password required")
            new_password_hashed = ph.hash(new_password)
            with open(PASSWORD_PATH, "w") as file:
                file.write(new_password_hashed)
            return {"message": "Success"}

        with open(PASSWORD_PATH, "r") as file:
            stored_password = file.read().strip()

        try:
            ph.verify(stored_password, password)
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid password")

        # 设置新密码
        new_password_hashed = ph.hash(new_password)
        with open(PASSWORD_PATH, "w") as file:
            file.write(new_password_hashed)

        return {"message": "Success"}
    except HTTPException as e:
        raise e
    except Exception as e:
        Logger.error(str(e))
        raise HTTPException(status_code=400, detail="Bad request")


@app.get("/api/server-info")
@limiter.limit("10/minute")
async def server_info(request: Request):
    verify_jwt(request)
    return {
        "message": "Success",
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
            "total": psutil.disk_usage("/").total / (1024 * 1024 * 1024),  # 磁盘总容量
            "used": psutil.disk_usage("/").used / (1024 * 1024 * 1024),  # 磁盘已使用容量
            "percent": psutil.disk_usage("/").percent,  # 磁盘使用百分比
        }
    }


@app.get("/api/config")
@limiter.limit("2/second")
async def get_config_list(request: Request):
    verify_jwt(request)
    try:
        files = os.listdir(config_path)
        cfg_files = [f for f in files if f.endswith(".toml")]

        if config_filename in cfg_files:
            cfg_files.remove(config_filename)
            cfg_files.insert(0, config_filename)

        return {"message": "Success", "cfg_files": cfg_files}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Not found")
    except Exception as e:
        Logger.error(str(e))
        raise HTTPException(status_code=400, detail="Bad request")


@app.get("/api/config/{cfg_filename}")
@limiter.limit("2/second")
async def get_config_file(request: Request, cfg_filename: str):
    verify_jwt(request)
    if not os.path.exists(config_path):
        raise HTTPException(status_code=404, detail="Not found")
    cfg_file_path = os.path.normpath(os.path.join(config_path, cfg_filename))
    if not cfg_filename.endswith(".toml"):
        raise HTTPException(status_code=400, detail="Bad request")
    if not cfg_file_path.startswith(config_path):
        raise HTTPException(status_code=400, detail="Bad request")

    try:
        with open(cfg_file_path, "r", encoding="UTF-8") as f:
            content = f.read()
        return {"message": "Success", "content": content}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Not found")
    except Exception as e:
        Logger.error(str(e))
        raise HTTPException(status_code=400, detail="Bad request")


@app.post("/api/config/{cfg_filename}")
@limiter.limit("10/minute")
async def edit_config_file(request: Request, cfg_filename: str):
    verify_jwt(request)
    verify_csrf_token(request)
    if not os.path.exists(config_path):
        raise HTTPException(status_code=404, detail="Not found")
    cfg_file_path = os.path.normpath(os.path.join(config_path, cfg_filename))
    if not cfg_filename.endswith(".toml"):
        raise HTTPException(status_code=400, detail="Bad request")
    if not cfg_file_path.startswith(config_path):
        raise HTTPException(status_code=400, detail="Bad request")
    try:
        body = await request.json()
        content = body["content"]
        with open(cfg_file_path, "w", encoding="UTF-8") as f:
            f.write(content)
        return {"message": "Success"}

    except Exception as e:
        Logger.error(str(e))
        raise HTTPException(status_code=400, detail="Bad request")


@app.get("/api/target")
@limiter.limit("2/second")
async def get_target_list(request: Request):
    target_list = await TargetInfo.all()
    target_list = [t for t in target_list if not t.target_id.startswith("TEST|")]
    return {"message": "Success", "targetList": target_list}


@app.get("/api/target/{target_id}")
@limiter.limit("2/second")
async def get_target(request: Request, target_id: str):
    try:
        target_info = await TargetInfo.get(target_id=target_id)
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="not found")

    return {
        "targetId": target_id,
        "modules": target_info.modules,
        "muted": target_info.muted,
        "customAdmins": target_info.custom_admins,
        "locale": target_info.locale,
        "targetData": target_info.target_data
    }


@app.get("/api/sender")
@limiter.limit("2/second")
async def get_sender_list(request: Request):
    sender_list = await SenderInfo.all()
    sender_list = [s for s in sender_list if not s.sender_id.startswith("TEST|")]
    return {"message": "Success", "targetList": sender_list}


@app.get("/api/sender/{sender_id}")
@limiter.limit("2/second")
async def get_sender(request: Request, sender_id: str):
    try:
        sender_info = await SenderInfo.get(sender_id=sender_id)
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="not found")

    return {
        "senderId": sender_id,
        "blocked": sender_info.blocked,
        "trusted": sender_info.trusted,
        "superUser": sender_info.superuser,
        "warns": sender_info.warns,
        "petal": sender_info.petal,
        "senderData": sender_info.sender_data,
    }


@app.get("/api/modules")
@limiter.limit("2/second")
async def get_module_list(request: Request):
    return {"modules": ModulesManager.return_modules_list()}


@app.get("/api/modules/{target_id}")
@limiter.limit("2/second")
async def get_target_modules(request: Request, target_id: str):
    target_info = (await TargetInfo.get_or_create(target_id=target_id))[0]
    target_from = "|".join(target_id.split("|")[:-2])
    modules = ModulesManager.return_modules_list(target_from=target_from)
    return {
        "targetId": target_id,
        "modules": {k: v for k, v in modules.items() if k in target_info.modules},
    }


@app.post("/api/modules/{target_id}/enable")
@limiter.limit("10/minute")
async def enable_modules(request: Request, target_id: str):
    try:
        verify_csrf_token(request)
        target_info = (await TargetInfo.get_or_create(target_id=target_id))[0]
        target_from = "|".join(target_id.split("|")[:-2])

        body = await request.json()
        modules = body["modules"]
        modules = modules if isinstance(modules, list) else [modules]
        modules = [
            m
            for m in modules
            if m in ModulesManager.return_modules_list(target_from=target_from)
        ]
        await target_info.config_module(modules, True)
        return {"message": "success"}
    except HTTPException as e:
        raise e
    except Exception as e:
        Logger.error(str(e))
        return HTTPException(status_code=400, detail="Bad request")


@app.post("/api/modules/{target_id}/disable")
@limiter.limit("10/minute")
async def disable_modules(request: Request, target_id: str):
    try:
        verify_csrf_token(request)
        target_info = (await TargetInfo.get_or_create(target_id=target_id))[0]
        target_from = "|".join(target_id.split("|")[:-2])

        body = await request.json()
        modules = body["modules"]
        modules = modules if isinstance(modules, list) else [modules]
        modules = [
            m
            for m in modules
            if m in ModulesManager.return_modules_list(target_from=target_from)
        ]
        await target_info.config_module(modules, False)
        return {"message": "success"}
    except HTTPException as e:
        raise e
    except Exception as e:
        Logger.error(str(e))
        return HTTPException(status_code=400, detail="Bad request")


@app.get("/api/locale/{locale}/{string}")
@limiter.limit("2/second")
async def get_locale(request: Request, locale: str, string: str):
    try:
        return {
            "locale": locale,
            "string": string,
            "translation": Locale(locale).t(string, False),
        }
    except TypeError:
        return HTTPException(status_code=404, detail="Not found")


@app.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket):
    await websocket.accept()

    if logs_history:
        expanded_history = ["\n".join(item) if isinstance(item, list) else item for item in logs_history]
        await websocket.send_text("\n".join(expanded_history))

    while True:
        today_logs = glob.glob(f"{logs_path}/*_{datetime.today().strftime("%Y-%m-%d")}.log")
        today_logs = [log for log in today_logs if "console" not in os.path.basename(log)]

        if today_logs:
            for log_file in today_logs:
                try:
                    current_line_count = 0
                    new_lines = []

                    with open(log_file, "r", encoding="utf-8") as f:
                        for i, line in enumerate(f):
                            if i >= last_file_line_count.get(log_file, 0):
                                if line:
                                    new_lines.append(line.rstrip())  # 移除行尾换行符
                            current_line_count = i + 1  # 记录当前文件行数

                    if new_lines:
                        processed_lines = []
                        for line in new_lines:
                            if is_log_line_valid(line):
                                # 新的日志行，结束之前的日志组
                                logs_history.append(line)
                            else:
                                # 非日志行，追加到最后一个日志行的列表
                                if logs_history and isinstance(
                                        logs_history[-1], str) and is_log_line_valid(logs_history[-1]):
                                    logs_history.append([logs_history.pop(), line])
                                elif logs_history and isinstance(logs_history[-1], list):
                                    logs_history[-1].append(line)
                                else:
                                    logs_history.append(line)  # 兜底处理
                            processed_lines.append(line)

                        logs_history.sort(
                            key=lambda line: (
                                extract_timestamp(
                                    line[0]) if isinstance(
                                    line,
                                    list) else extract_timestamp(line)) or datetime.min)
                        # 发送日志数据，展开 logs_history 里的列表
                        expanded_logs = [
                            "\n".join(item) if isinstance(
                                item, list) else item for item in processed_lines]
                        await websocket.send_text("\n".join(expanded_logs))

                        # 维护 logs_history 长度
                        while len(logs_history) > MAX_LOG_HISTORY:
                            logs_history.pop(0)

                        # 清理无效日志行（直接移除整个列表）
                        while logs_history and not is_log_line_valid(logs_history[0]):
                            logs_history.pop(0)

                    last_file_line_count[log_file] = current_line_count
                except Exception:
                    continue

        await asyncio.sleep(0.1)


def is_log_line_valid(line: str) -> bool:
    log_pattern = r"^\[.+\]\[[a-zA-Z0-9\._]+:[a-zA-Z0-9\._]+:\d+\]\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\]\[[A-Z]+\]:"
    return bool(re.match(log_pattern, line))


def extract_timestamp(log_line: str):
    log_time_pattern = r"\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]"
    match = re.search(log_time_pattern, log_line)
    if match:
        return datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S")
    return None


if __name__ == "__main__" and Config("enable", True, table_name="bot_web"):
    Info.client_name = client_name
    uvicorn.run(app, port=API_PORT, log_level="info")
