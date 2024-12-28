import os
import platform
import sys
import time
import uuid
from datetime import datetime, timedelta, UTC

import jwt
import uvicorn
from argon2 import PasswordHasher
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles

from bots.api.info import client_name
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


def verify_access_token(request: Request):
    if request.url.path == "/favicon.ico":
        return
    if not ACCESS_TOKEN:
        return

    auth_header = request.headers.get("Authorization")
    if not auth_header or auth_header != f"Bearer {ACCESS_TOKEN}":
        raise HTTPException(status_code=403, detail="forbidden")


app = FastAPI(dependencies=[Depends(verify_access_token)])
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
