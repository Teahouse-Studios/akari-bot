import asyncio
import glob
import os
import platform
import re
import sys
import traceback
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, UTC

import jwt
import psutil
import uvicorn
import orjson as json
from argon2 import PasswordHasher
from cpuinfo import get_cpu_info
from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi import Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.wsgi import WSGIMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from flask import Flask, send_from_directory
from jwt.exceptions import ExpiredSignatureError
from slowapi import Limiter
from slowapi.util import get_remote_address
from tortoise.expressions import Q

sys.path.append(os.getcwd())

from bots.web.info import *  # noqa: E402
from bots.web.message import MessageSession  # noqa: E402
from bots.web.utils import find_available_port, generate_webui_config  # noqa: E402
from core.bot_init import init_async  # noqa: E402
from core.builtins import PrivateAssets, Temp  # noqa: E402
from core.config import Config  # noqa: E402
from core.constants import config_filename  # noqa: E402
from core.constants.path import assets_path, config_path, logs_path, webui_path  # noqa: E402
from core.database.models import AnalyticsData, SenderInfo, TargetInfo, MaliciousLoginRecords  # noqa: E402
from core.database.local import CSRF_TOKEN_EXPIRY, CSRFTokenRecords  # noqa: E402
from core.extra.scheduler import load_extra_schedulers  # noqa: E402
from core.i18n import Locale  # noqa: E402
from core.loader import ModulesManager  # noqa: E402
from core.logger import Logger  # noqa: E402
from core.parser.message import parser  # noqa: E402
from core.queue import JobQueue  # noqa: E402
from core.scheduler import Scheduler  # noqa: E402
from core.terminate import cleanup_sessions  # noqa: E402
from core.types import MsgInfo, Session  # noqa: E402
from core.utils.info import Info  # noqa: E402

started_time = datetime.now()
webui_index = os.path.join(webui_path, "index.html")
PrivateAssets.set(os.path.join(assets_path, "private", "web"))

default_locale = Config("default_locale", cfg_type=str)
enable_https = Config("enable_https", default=False, table_name="bot_web")

WEB_HOST = Config("web_host", "127.0.0.1", table_name="bot_web")
WEB_PORT = Config("web_port", 8081, table_name="bot_web")

ALLOW_ORIGINS = Config("allow_origins", default=[], secret=True, table_name="bot_web")
JWT_SECRET = Config("jwt_secret", cfg_type=str, secret=True, table_name="bot_web")
LOGIN_MAX_ATTEMPTS = Config("login_max_attempts", default=5, table_name="bot_web")
PASSWORD_PATH = os.path.join(PrivateAssets.path, ".password")
LOGIN_BLOCK_DURATION = 3600
MAX_LOG_HISTORY = 1000

web_port = find_available_port(WEB_PORT, host=WEB_HOST)
protocol = "https" if enable_https else "http"
ALLOW_ORIGINS.append(f"{protocol}://{WEB_HOST}:{web_port}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_async(start_scheduler=False)
    load_extra_schedulers()
    Scheduler.start()
    await JobQueue.secret_append_ip()
    await JobQueue.web_render_status()
    if os.path.exists(webui_index):
        Logger.info(f"Visit AkariBot WebUI: {protocol}://{WEB_HOST}:{web_port}/webui")
    yield
    await cleanup_sessions()
    sys.exit()

app = FastAPI(lifespan=lifespan)
limiter = Limiter(key_func=get_remote_address)
ph = PasswordHasher()

login_failed_attempts = defaultdict(list)
last_file_line_count = {}
logs_history = []


async def verify_csrf_token(request: Request):
    auth_token = request.cookies.get("deviceToken")
    csrf_token = request.headers.get("X-XSRF-TOKEN")
    if not csrf_token:
        raise HTTPException(status_code=403, detail="Missing CSRF token")

    token_entry = await CSRFTokenRecords.get_or_none(csrf_token=csrf_token, device_token=auth_token)
    if not token_entry:
        raise HTTPException(status_code=403, detail="Invalid CSRF token")

    if (datetime.now(UTC) - token_entry.timestamp).total_seconds() > CSRF_TOKEN_EXPIRY:
        await token_entry.delete()
        raise HTTPException(status_code=403, detail="CSRF token expired")

    return {"message": "Success"}


def verify_jwt(request: Request):
    auth_token = request.cookies.get("deviceToken")
    if not auth_token:
        raise HTTPException(status_code=401, detail="Invalid request")

    try:
        payload = jwt.decode(auth_token, JWT_SECRET, algorithms=["HS256"])
        if os.path.exists(PASSWORD_PATH):
            with open(PASSWORD_PATH, "rb") as f:
                last_updated = json.loads(f.read()).get("last_updated")

            if last_updated and payload["iat"] < last_updated:
                raise ExpiredSignatureError

        return {"message": "Success", "payload": payload}

    except ExpiredSignatureError:
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


@app.get("/api")
@limiter.limit("2/second")
async def api_root(request: Request):
    return {"message": "Hello, AkariBot!"}


@app.get("/api/verify-token")
@limiter.limit("2/second")
async def verify_token(request: Request):
    return verify_jwt(request)


@app.get("/api/get-csrf-token")
@limiter.limit("2/second")
async def set_csrf_token(request: Request):
    verify_jwt(request)
    auth_token = request.cookies.get("deviceToken")
    csrf_token = await CSRFTokenRecords.generate_csrf_token(device_token=auth_token)

    return {"message": "Success", "csrf_token": csrf_token}


@app.post("/api/auth")
@limiter.limit("10/minute")
async def auth(request: Request, response: Response):
    ip = request.client.host
    if await MaliciousLoginRecords.check_blocked(ip):
        raise HTTPException(status_code=403, detail="This IP has been blocked")

    try:
        if not os.path.exists(PASSWORD_PATH):
            payload = {
                "exp": datetime.now(UTC) + timedelta(hours=24),  # 过期时间
                "iat": datetime.now(UTC),  # 签发时间
                "iss": "auth-api"  # 签发者
            }
            jwt_token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")

            response.set_cookie(
                key="deviceToken",
                value=jwt_token,
                httponly=True,
                secure=enable_https,
                samesite="strict",
                expires=datetime.now(UTC) + timedelta(hours=24)
            )
            return {"message": "Success", "no_password": True}

        body = await request.json()
        password = body.get("password", "")
        remember = body.get("remember", False)

        with open(PASSWORD_PATH, "rb") as file:
            password_data = json.loads(file.read())

        try:
            ph.verify(password_data.get("password", ""), password)
        except Exception:
            now = datetime.now(UTC)
            login_failed_attempts[ip] = [t for t in login_failed_attempts[ip] if (now - t).total_seconds() < 600]
            login_failed_attempts[ip].append(now)

            if len(login_failed_attempts[ip]) >= LOGIN_MAX_ATTEMPTS:
                await MaliciousLoginRecords.create(ip_address=ip, blocked_until=now + timedelta(seconds=LOGIN_BLOCK_DURATION))
                login_failed_attempts[ip].clear()
                raise HTTPException(status_code=403, detail="This IP has been blocked")

            raise HTTPException(status_code=401, detail="Invalid password")

        login_failed_attempts.pop(ip, None)

        payload = {
            "exp": datetime.now(UTC) + (timedelta(days=365) if remember else timedelta(hours=24)),
            "iat": datetime.now(UTC),
            "iss": "auth-api"
        }
        jwt_token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")

        response.set_cookie(
            key="deviceToken",
            value=jwt_token,
            httponly=True,
            secure=enable_https,
            samesite="strict",
            expires=datetime.now(UTC) + timedelta(hours=24)
        )
        return {"message": "Success", "no_password": True}

    except HTTPException as e:
        raise e
    except Exception:
        Logger.error(traceback.format_exc())
        raise HTTPException(status_code=400, detail="Bad request")


@app.post("/api/change-password")
@limiter.limit("10/minute")
async def change_password(request: Request, response: Response):
    try:
        verify_jwt(request)
        await verify_csrf_token(request)
        body = await request.json()
        new_password = body.get("new_password", "")
        password = body.get("password", "")

        if not os.path.exists(PASSWORD_PATH):
            if new_password == "":
                raise HTTPException(status_code=400, detail="New password required")

            password_data = {
                "password": ph.hash(new_password),
                "last_updated": datetime.now().timestamp()
            }
            with open(PASSWORD_PATH, "wb") as file:
                file.write(json.dumps(password_data))
            response.delete_cookie("deviceToken")
            return {"message": "Success"}

        with open(PASSWORD_PATH, "rb") as file:
            password_data = json.loads(file.read())

        try:
            ph.verify(password_data.get("password", ""), password)
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid password")

        password_data["password"] = ph.hash(new_password)
        password_data["last_updated"] = datetime.now().timestamp()

        with open(PASSWORD_PATH, "wb") as file:
            file.write(json.dumps(password_data))

        response.delete_cookie("deviceToken")
        return {"message": "Success"}
    except HTTPException as e:
        raise e
    except Exception:
        Logger.error(traceback.format_exc())
        raise HTTPException(status_code=400, detail="Bad request")


@app.post("/api/clear-password")
@limiter.limit("10/minute")
async def clear_password(request: Request, response: Response):
    try:
        verify_jwt(request)
        await verify_csrf_token(request)
        body = await request.json()
        password = body.get("password", "")

        if not os.path.exists(PASSWORD_PATH):
            raise HTTPException(status_code=404, detail="Password not set")

        with open(PASSWORD_PATH, "rb") as file:
            password_data = json.loads(file.read())

        try:
            ph.verify(password_data.get("password", ""), password)
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid password")

        os.remove(PASSWORD_PATH)
        response.delete_cookie("deviceToken")
        return {"message": "Success"}
    except HTTPException as e:
        raise e
    except Exception:
        Logger.error(traceback.format_exc())
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
            "boot_time": psutil.boot_time()
        },
        "bot": {
            "running_time": (datetime.now() - started_time).total_seconds(),
            "python_version": platform.python_version(),
            "version": Info.version,
            "web_render_local_status": Info.web_render_local_status,
            "web_render_status": Info.web_render_status
        },
        "cpu": {
            "cpu_brand": get_cpu_info()["brand_raw"],
            "cpu_percent": psutil.cpu_percent(interval=1)
        },
        "memory": {
            "total": psutil.virtual_memory().total / (1024 * 1024),
            "used": psutil.virtual_memory().used / (1024 * 1024),
            "percent": psutil.virtual_memory().percent
        },
        "disk": {
            "total": psutil.disk_usage("/").total / (1024 * 1024 * 1024),
            "used": psutil.disk_usage("/").used / (1024 * 1024 * 1024),
            "percent": psutil.disk_usage("/").percent
        }
    }


@app.get("/api/analytics")
@limiter.limit("2/second")
async def get_analytics(request: Request, days: int = Query(1)):
    verify_jwt(request)
    try:
        now = datetime.now()
        past = now - timedelta(days=days)
        data = await AnalyticsData.get_values_by_times(now, past)
        count = await AnalyticsData.get_count_by_times(now, past)
        past_past = now - timedelta(days=2 * days)
        past_count = await AnalyticsData.get_count_by_times(past, past_past)
        try:
            change_rate = round((count - past_count) / past_count, 2)
        except ZeroDivisionError:
            change_rate = 0.00

        return {"count": count, "change_rate": change_rate, "data": data}

    except Exception:
        Logger.error(traceback.format_exc())
        raise HTTPException(status_code=400, detail="Bad request")


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
    except Exception:
        Logger.error(traceback.format_exc())
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
    except Exception:
        Logger.error(traceback.format_exc())
        raise HTTPException(status_code=400, detail="Bad request")


@app.post("/api/config/{cfg_filename}")
@limiter.limit("10/minute")
async def edit_config_file(request: Request, cfg_filename: str):
    try:
        verify_jwt(request)
        await verify_csrf_token(request)
        if not os.path.exists(config_path):
            raise HTTPException(status_code=404, detail="Not found")
        cfg_file_path = os.path.normpath(os.path.join(config_path, cfg_filename))
        if not cfg_filename.endswith(".toml"):
            raise HTTPException(status_code=400, detail="Bad request")
        if not cfg_file_path.startswith(config_path):
            raise HTTPException(status_code=400, detail="Bad request")

        body = await request.json()
        content = body["content"]
        with open(cfg_file_path, "w", encoding="UTF-8") as f:
            f.write(content)
        return {"message": "Success"}

    except HTTPException as e:
        raise e
    except Exception:
        Logger.error(traceback.format_exc())
        raise HTTPException(status_code=400, detail="Bad request")


@app.get("/api/target")
@limiter.limit("2/second")
async def get_target_list(
    request: Request,
    prefix: str = Query(None),
    status: str = Query(None, pattern=r"^(muted|blocked)?$"),
    id: str = Query(None),
    page: int = Query(1, gt=0),
    size: int = Query(20, gt=0, le=100)
):
    try:
        verify_jwt(request)

        query = TargetInfo.all()
        filters = Q()
        if prefix:
            filters &= Q(target_id__startswith=f"{prefix}|")
        if status == "muted":
            filters &= Q(muted=True)
        if status == "blocked":
            filters &= Q(blocked=True)
        if id:
            filters &= Q(target_id__icontains=id)

        query = query.filter(filters)
        total = await query.count()
        results = await query.offset((page - 1) * size).limit(size)

        return {
            "message": "Success",
            "target_list": results,
            "total": total
        }
    except HTTPException as e:
        raise e
    except Exception:
        Logger.error(traceback.format_exc())
        raise HTTPException(status_code=400, detail="Bad request")


@app.get("/api/target/{target_id}")
@limiter.limit("2/second")
async def get_target_info(request: Request, target_id: str):
    try:
        verify_jwt(request)
        target_info = await TargetInfo.get_by_target_id(target_id, create=False)
        if not target_info:
            raise HTTPException(status_code=404, detail="Not found")
        return {"message": "Success", "target_info": target_info}
    except HTTPException as e:
        raise e
    except Exception:
        Logger.error(traceback.format_exc())
        raise HTTPException(status_code=400, detail="Bad request")


@app.post("/api/target/{target_id}/edit")
@limiter.limit("10/minute")
async def edit_target_info(request: Request, target_id: str):
    try:
        verify_jwt(request)
        await verify_csrf_token(request)

        target_info = await TargetInfo.get_by_target_id(target_id)
        body = await request.json()
        blocked = body.get("blocked")
        muted = body.get("muted")
        locale = body.get("locale")
        blocked = body.get("blocked")
        modules = body.get("modules")
        custom_admins = body.get("custom_admins")
        banned_users = body.get("banned_users")
        target_data = body.get("target_data")

        if blocked is not None and not isinstance(blocked, bool):
            raise HTTPException(status_code=400, detail="'blocked' must be bool")
        if muted is not None and not isinstance(muted, bool):
            raise HTTPException(status_code=400, detail="'muted' must be bool")
        if locale is not None and not isinstance(locale, str):
            raise HTTPException(status_code=400, detail="'locale' must be str")
        if modules is not None and not isinstance(modules, list):
            raise HTTPException(status_code=400, detail="'modules' must be list")
        if custom_admins is not None and not isinstance(custom_admins, list):
            raise HTTPException(status_code=400, detail="'custom_admins' must be list")
        if banned_users is not None and not isinstance(banned_users, list):
            raise HTTPException(status_code=400, detail="'banned_users' must be list")
        if target_data is not None and not isinstance(target_data, dict):
            raise HTTPException(status_code=400, detail="'target_data' must be dict")

        if blocked is not None:
            target_info.blocked = blocked
        if muted is not None:
            target_info.muted = muted
        if locale is not None:
            target_info.locale = locale
        if modules is not None:
            target_info.modules = modules
        if custom_admins is not None:
            target_info.custom_admins = custom_admins
        if banned_users is not None:
            target_info.banned_users = banned_users
        if target_data is not None:
            target_info.target_data = target_data
        await target_info.save()

        return {"message": "Success"}
    except HTTPException as e:
        raise e
    except Exception:
        Logger.error(traceback.format_exc())
        raise HTTPException(status_code=400, detail="Bad request")


@app.post("/api/target/{target_id}/delete")
@limiter.limit("10/minute")
async def delete_target_info(request: Request, target_id: str):
    try:
        verify_jwt(request)
        await verify_csrf_token(request)
        target_info = await TargetInfo.get_by_target_id(target_id, create=False)
        if target_info:
            await target_info.delete()
        return {"message": "Success"}
    except HTTPException as e:
        raise e
    except Exception:
        Logger.error(traceback.format_exc())
        raise HTTPException(status_code=400, detail="Bad request")


@app.get("/api/sender")
@limiter.limit("2/second")
async def get_sender_list(request: Request,
                          prefix: str = Query(None),
                          status: str = Query(None, pattern=r"^(superuser|trusted|blocked)?$"),
                          id: str = Query(None),
                          page: int = Query(1, gt=0),
                          size: int = Query(20, gt=0, le=100)
                          ):
    try:
        verify_jwt(request)

        query = SenderInfo.all()
        filters = Q()
        if prefix:
            filters &= Q(sender_id__startswith=f"{prefix}|")
        if status == "superuser":
            filters &= Q(superuser=True)
        elif status == "trusted":
            filters &= Q(trusted=True)
        elif status == "blocked":
            filters &= Q(blocked=True)
        if id:
            filters &= Q(sender_id__icontains=id)

        query = query.filter(filters)
        total = await query.count()
        results = await query.offset((page - 1) * size).limit(size)

        return {
            "message": "Success",
            "sender_list": results,
            "total": total
        }
    except HTTPException as e:
        raise e
    except Exception:
        Logger.error(traceback.format_exc())
        raise HTTPException(status_code=400, detail="Bad request")


@app.get("/api/sender/{sender_id}")
@limiter.limit("2/second")
async def get_sender_info(request: Request, sender_id: str):
    try:
        verify_jwt(request)
        sender_info = await SenderInfo.get_by_sender_id(sender_id, create=False)
        if not sender_info:
            raise HTTPException(status_code=404, detail="Not found")
        return {"message": "Success", "sender_info": sender_info}
    except HTTPException as e:
        raise e
    except Exception:
        Logger.error(traceback.format_exc())
        raise HTTPException(status_code=400, detail="Bad request")


@app.post("/api/sender/{sender_id}/edit")
@limiter.limit("10/minute")
async def edit_sender_info(request: Request, sender_id: str):
    try:
        verify_jwt(request)
        await verify_csrf_token(request)

        sender_info = await SenderInfo.get_by_sender_id(sender_id)
        body = await request.json()
        superuser = body.get("superuser")
        trusted = body.get("trusted")
        blocked = body.get("blocked")
        warns = body.get("warns")
        petal = body.get("petal")
        sender_data = body.get("sender_data")

        if superuser is not None and not isinstance(superuser, bool):
            raise HTTPException(status_code=400, detail="'superuser' must be bool")
        if trusted is not None and not isinstance(trusted, bool):
            raise HTTPException(status_code=400, detail="'trusted' must be bool")
        if blocked is not None and not isinstance(blocked, bool):
            raise HTTPException(status_code=400, detail="'blocked' must be bool")
        if warns is not None and not isinstance(warns, int):
            raise HTTPException(status_code=400, detail="'warns' must be int")
        if petal is not None and not isinstance(petal, int):
            raise HTTPException(status_code=400, detail="'petal' must be int")
        if sender_data is not None and not isinstance(sender_data, dict):
            raise HTTPException(status_code=400, detail="'sender_data' must be dict")

        if superuser is not None:
            sender_info.superuser = superuser
        if trusted is not None:
            sender_info.trusted = trusted
        if blocked is not None:
            sender_info.blocked = blocked
        if warns is not None:
            sender_info.warns = warns
        if petal is not None:
            sender_info.petal = petal
        if sender_data is not None:
            sender_info.sender_data = sender_data
        await sender_info.save()

        return {"message": "Success"}
    except HTTPException as e:
        raise e
    except Exception:
        Logger.error(traceback.format_exc())
        raise HTTPException(status_code=400, detail="Bad request")


@app.post("/api/sender/{sender_id}/delete")
@limiter.limit("10/minute")
async def delete_sender_info(request: Request, sender_id: str):
    try:
        verify_jwt(request)
        await verify_csrf_token(request)
        sender_info = await SenderInfo.get_by_sender_id(sender_id, create=False)
        if sender_info:
            await sender_info.delete()
        return {"message": "Success"}
    except HTTPException as e:
        raise e
    except Exception:
        Logger.error(traceback.format_exc())
        raise HTTPException(status_code=400, detail="Bad request")


@app.get("/api/modules_list")
@limiter.limit("2/second")
async def get_modules_list(request: Request):
    try:
        verify_jwt(request)
        modules = {k: v.to_dict() for k, v in ModulesManager.return_modules_list().items()}
        modules = {k: v for k, v in modules.items() if v.get('load', True) and not v.get('base', False)}

        modules_list = []
        for module in modules.values():
            modules_list.append(module["bind_prefix"])
        return {"message": "Success", "modules": modules}
    except HTTPException as e:
        raise e
    except Exception:
        Logger.error(traceback.format_exc())
        raise HTTPException(status_code=400, detail="Bad request")


@app.get("/api/modules")
@limiter.limit("2/second")
async def get_modules_info(request: Request, locale: str = Query(default_locale)):
    try:
        verify_jwt(request)
        modules = {k: v.to_dict() for k, v in ModulesManager.return_modules_list().items()}
        modules = {k: v for k, v in modules.items() if v.get('load', True) and not v.get('base', False)}

        for module in modules.values():
            if 'desc' in module and module.get('desc'):
                module['desc'] = Locale(locale).t_str(module['desc'])
        return {"message": "Success", "modules": modules}
    except HTTPException as e:
        raise e
    except Exception:
        Logger.error(traceback.format_exc())
        raise HTTPException(status_code=400, detail="Bad request")


@app.get("/api/modules/{module}")
@limiter.limit("2/second")
async def get_module_info(request: Request, module: str, locale: str = Query(default_locale)):
    try:
        verify_jwt(request)
        modules = {k: v.to_dict() for k, v in ModulesManager.return_modules_list().items()}
        modules = {k: v for k, v in modules.items() if v.get('load', True) and not v.get('base', False)}

        for m in modules.values():
            if module == m["bind_prefix"]:
                return {"message": "Success", "modules": m}
        raise HTTPException(status_code=404, detail="Not found")
    except HTTPException as e:
        raise e
    except Exception:
        Logger.error(traceback.format_exc())
        raise HTTPException(status_code=400, detail="Bad request")


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()
    Temp.data['web_chat_websocket'] = websocket
    try:
        while True:
            rmessage = await websocket.receive_text()
            if rmessage:
                message = json.loads(rmessage)
                msg = MessageSession(
                    target=MsgInfo(
                        target_id=f"{target_prefix}|0",
                        sender_id=f"{sender_prefix}|0",
                        sender_name="Console",
                        target_from=target_prefix,
                        sender_from=sender_prefix,
                        client_name=client_name,
                        message_id=message["id"],
                    ),
                    session=Session(
                        message=message, target=f"{target_prefix}|0", sender=f"{sender_prefix}|0"
                    ))
                asyncio.create_task(parser(msg))
    except WebSocketDisconnect:
        pass
    except Exception:
        Logger.error(traceback.format_exc())
        await websocket.close()
    finally:
        if 'web_chat_websocket' in Temp.data:
            del Temp.data['web_chat_websocket']


@app.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket):
    await websocket.accept()

    try:
        if logs_history:
            expanded_history = ["\n".join(item) if isinstance(item, list) else item for item in logs_history]
            await websocket.send_text("\n".join(expanded_history))

        while True:
            today_logs = glob.glob(f"{logs_path}/*_{datetime.today().strftime("%Y-%m-%d")}.log")
            today_logs = [log for log in today_logs if "console" not in os.path.basename(log)]
            today_logs.sort(
                key=lambda line: (
                    extract_timestamp(
                        line[0]) if isinstance(
                        line,
                        list) else extract_timestamp(line)) or datetime.min)
            if today_logs:
                for log_file in today_logs:
                    current_line_count = 0
                    new_lines = []

                    with open(log_file, "r", encoding="utf-8") as f:
                        for i, line in enumerate(f):
                            if i >= last_file_line_count.get(log_file, 0):
                                if line:
                                    new_lines.append(line.rstrip())
                            current_line_count = i + 1

                    if new_lines:
                        processed_lines = []
                        for line in new_lines:
                            if is_log_line_valid(line):
                                logs_history.append(line)
                            else:
                                if logs_history and isinstance(
                                        logs_history[-1], str) and is_log_line_valid(logs_history[-1]):
                                    logs_history.append([logs_history.pop(), line])
                                elif logs_history and isinstance(logs_history[-1], list):
                                    logs_history[-1].append(line)
                                else:
                                    logs_history.append(line)
                            processed_lines.append(line)

                        logs_history.sort(
                            key=lambda line: (
                                extract_timestamp(
                                    line[0]) if isinstance(
                                    line,
                                    list) else extract_timestamp(line)) or datetime.min)
                        expanded_logs = [
                            "\n".join(item) if isinstance(
                                item, list) else item for item in processed_lines]
                        await websocket.send_text("\n".join(expanded_logs))

                        while len(logs_history) > MAX_LOG_HISTORY:
                            logs_history.pop(0)

                    last_file_line_count[log_file] = current_line_count

            await asyncio.sleep(0.1)
    except WebSocketDisconnect:
        pass
    except Exception:
        Logger.error(traceback.format_exc())
        await websocket.close()


def is_log_line_valid(line: str) -> bool:
    log_pattern = r"^\[.+\]\[[a-zA-Z0-9\._]+:[a-zA-Z0-9\._]+:\d+\]\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\]\[[A-Z]+\]:"
    return bool(re.match(log_pattern, line))


def extract_timestamp(log_line: str):
    log_time_pattern = r"\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]"
    match = re.search(log_time_pattern, log_line)
    if match:
        return datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S")
    return None


@app.post("/api/restart")
async def restart_bot(request: Request):
    verify_jwt(request)
    await verify_csrf_token(request)

    asyncio.create_task(restart())
    return {"message": "Success"}


async def restart():
    await asyncio.sleep(1)
    await cleanup_sessions()
    os._exit(233)

if os.path.exists(webui_index):
    flask_app = Flask(__name__)

    @flask_app.route("/")
    @flask_app.route("/<path:path>")
    def static_files(path=None):
        return send_from_directory(webui_path, "index.html")

    app.mount("/webui", WSGIMiddleware(flask_app))

    @app.get("/webui")
    async def redirect_webui():
        return RedirectResponse(url="/webui/")


@app.get("/{path:path}")
async def redirect_root(path: str = ""):
    if os.path.exists(webui_index):
        if not path:
            return RedirectResponse(url="/webui")
        if path.startswith("/api") or path.startswith("/webui"):
            return RedirectResponse(url=path)
    else:
        if not path:
            return RedirectResponse(url="/api")
        if path.startswith("/api"):
            return RedirectResponse(url=path)
    static_path = os.path.normpath(os.path.join(webui_path, path))
    if not static_path.startswith(webui_path) or not os.path.exists(static_path):
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(static_path)


if Config("enable", True, table_name="bot_web"):
    Info.client_name = client_name
    web_port = find_available_port(WEB_PORT)
    if web_port == 0:
        Logger.error("API port is disabled, abort to run.")
        sys.exit(0)
    if not enable_https:
        Logger.warning("HTTPS is disabled. HTTP mode is insecure and should only be used in trusted environments.")

    if os.path.exists(webui_index):
        generate_webui_config(web_port, WEB_HOST, enable_https, default_locale)

    uvicorn.run(app, host=WEB_HOST, port=web_port, log_level="info")
