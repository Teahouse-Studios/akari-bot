from datetime import datetime
import os
import platform
import sys
import time

import hashlib
import psutil
import uvicorn
from cpuinfo import get_cpu_info
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware

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


PrivateAssets.set(os.path.join(assets_path, "private", "api"))
app = FastAPI()
started_time = datetime.now()

origins = [
    "http://localhost:8080",
    "http://127.0.0.1:8080",
]  # temp


app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    await init_async(start_scheduler=False)
    load_extra_schedulers()
    Scheduler.start()
    await JobQueue.secret_append_ip()
    await JobQueue.web_render_status()


@app.post("/auth")
async def auth(request: Request):
    try:
        password_path = os.path.join(PrivateAssets.path, ".password")
        if not os.path.exists(password_path):
            return {"message": "success"}

        with open(password_path, "r") as file:
            stored_password = file.read().strip()

        body = await request.json()
        password = body["password"]
        password = hashlib.sha256(password.encode()).hexdigest()
        if stored_password != password:
            raise HTTPException(status_code=401, detail="invalid password")
        return {"message": "success"}
    except HTTPException as e:
        raise e
    except Exception:
        return HTTPException(status_code=400, detail="bad request")


@app.post("/auth/change")
async def changepassword(request: Request):
    try:
        password_path = os.path.join(PrivateAssets.path, ".password")

        body = await request.json()
        new_password = body.get("new_password", "")
        password = body.get("password", "")

        if not os.path.exists(password_path):
            if new_password == "":
                raise HTTPException(status_code=400, detail="new password required")
            new_password = hashlib.sha256(new_password.encode()).hexdigest()
            with open(password_path, "w") as file:
                file.write(new_password)
            return {"message": "success"}

        with open(password_path, "r") as file:
            stored_password = file.read().strip()

        password = hashlib.sha256(password.encode()).hexdigest()
        if stored_password != password:
            raise HTTPException(status_code=401, detail="invalid password")

        if new_password == "":
            os.remove(password_path)
            return {"message": "success"}

        new_password = hashlib.sha256(new_password.encode()).hexdigest()
        with open(password_path, "w") as file:
            file.write(new_password)

        return {"message": "success"}
    except HTTPException as e:
        raise e
    except Exception:
        return HTTPException(status_code=400, detail="bad request")


@app.get("/serverinfo")
async def get_server_info():
    timediff = str(datetime.now() - started_time).split(".")[0]
    python_version = str(platform.python_version())
    cpu_brand = get_cpu_info()["brand_raw"]
    cpu_usage = psutil.cpu_percent()
    ram = int(psutil.virtual_memory().total / (1024 * 1024))
    swap = int(psutil.swap_memory().total / (1024 * 1024))
    disk = int(psutil.disk_usage("/").used / (1024 * 1024 * 1024))
    disk_total = int(psutil.disk_usage("/").total / (1024 * 1024 * 1024))
    return {
        "message": "Success",
        "timeDiff": timediff,
        "pythonVersion": python_version,
        "cpuBrand": cpu_brand,
        "cpuUsage": cpu_usage,
        "ram": ram,
        "swap": swap,
        "disk": disk,
        "diskTotal": disk_total,
    }


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
    except Exception:
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
