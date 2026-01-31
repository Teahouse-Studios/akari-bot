import asyncio
import os
import platform
from datetime import datetime, timedelta

import psutil
from cpuinfo import get_cpu_info
from fastapi import HTTPException, Request, Query
from fastapi.responses import Response
from tortoise.expressions import Q

from bots.web.client import app, limiter, enable_https
from core.builtins.utils import command_prefix
from core.config import Config
from core.constants import config_filename
from core.constants.path import config_path
from core.database.models import AnalyticsData, SenderInfo, TargetInfo
from core.logger import Logger
from core.queue.client import JobQueueClient
from .auth import verify_jwt

started_time = datetime.now()


default_locale = Config("default_locale", cfg_type=str)


@app.get("/api")
@limiter.limit("10/second")
async def api_root(request: Request):
    return {"message": "Hello, AkariBot!"}


@app.get("/api/init")
@limiter.limit("10/second")
async def get_config(request: Request):
    return {"enable_https": enable_https,
            "command_prefix": command_prefix[0],
            "locale": Config("default_locale", cfg_type=str),
            "heartbeat_interval": Config("heartbeat_interval", 30, table_name="bot_web"),
            "heartbeat_timeout": Config("heartbeat_timeout", 5, table_name="bot_web"),
            "heartbeat_attempt": Config("heartbeat_attempt", 3, table_name="bot_web")
            }


@app.get("/api/server-info")
async def server_info(request: Request):
    verify_jwt(request)
    return {
        "os": {
            "system": platform.system(),
            "version": platform.version(),
            "machine": platform.machine(),
            "boot_time": psutil.boot_time()
        },
        "bot": {
            "running_time": (datetime.now() - started_time).total_seconds(),
            "python_version": platform.python_version(),
            "version": await JobQueueClient.get_bot_version(),
            "web_render_status": await JobQueueClient.get_web_render_status()
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
        Logger.exception()
        raise HTTPException(status_code=400, detail="Bad request")


@app.get("/api/config")
async def get_config_list(request: Request):
    verify_jwt(request)
    try:
        files = [c.name for c in config_path.iterdir()]
        cfg_files = sorted([f for f in files if f.endswith(".toml")])

        if config_filename in cfg_files:
            cfg_files.remove(config_filename)
            cfg_files.insert(0, config_filename)

        return {"cfg_files": cfg_files}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Not found")
    except Exception:
        Logger.exception()
        raise HTTPException(status_code=400, detail="Bad request")


@app.get("/api/config/{cfg_filename}")
async def get_config_file(request: Request, cfg_filename: str):
    verify_jwt(request)
    if not config_path.exists():
        raise HTTPException(status_code=404, detail="Not found")
    cfg_file_path = config_path / cfg_filename
    if not cfg_filename.endswith(".toml"):
        raise HTTPException(status_code=400, detail="Bad request")
    if not str(cfg_file_path).startswith(str(config_path)):
        raise HTTPException(status_code=400, detail="Bad request")

    try:
        with open(cfg_file_path, "r", encoding="UTF-8") as f:
            content = f.read()
        return {"content": content}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Not found")
    except Exception:
        Logger.exception()
        raise HTTPException(status_code=400, detail="Bad request")


@app.put("/api/config/{cfg_filename}")
async def edit_config_file(request: Request, cfg_filename: str):
    ip = request.client.host
    try:
        verify_jwt(request)

        if not config_path.exists():
            raise HTTPException(status_code=404, detail="Not found")
        cfg_file_path = config_path / cfg_filename
        if not cfg_filename.endswith(".toml"):
            raise HTTPException(status_code=400, detail="Bad request")
        if not str(cfg_file_path).startswith(str(config_path)):
            raise HTTPException(status_code=400, detail="Bad request")

        body = await request.json()
        content = body["content"]
        with open(cfg_file_path, "w", encoding="UTF-8") as f:
            f.write(content)
        Logger.info(f"[WebUI] {ip} has edited the config file: {cfg_filename}")
        return Response(status_code=204)

    except HTTPException as e:
        raise e
    except Exception:
        Logger.exception()
        raise HTTPException(status_code=400, detail="Bad request")


@app.get("/api/target")
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
            "target_list": results,
            "total": total
        }
    except HTTPException as e:
        raise e
    except Exception:
        Logger.exception()
        raise HTTPException(status_code=400, detail="Bad request")


@app.get("/api/target/{target_id}")
async def get_target_info(request: Request, target_id: str):
    try:
        verify_jwt(request)
        target_info = await TargetInfo.get_by_target_id(target_id, create=False)
        if not target_info:
            raise HTTPException(status_code=404, detail="Not found")
        return {"target_info": target_info}
    except HTTPException as e:
        raise e
    except Exception:
        Logger.exception()
        raise HTTPException(status_code=400, detail="Bad request")


@app.patch("/api/target/{target_id}")
async def edit_target_info(request: Request, target_id: str):
    ip = request.client.host
    try:
        verify_jwt(request)

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
            raise HTTPException(status_code=400, detail="\"blocked\" must be bool")
        if muted is not None and not isinstance(muted, bool):
            raise HTTPException(status_code=400, detail="\"muted\" must be bool")
        if locale is not None and not isinstance(locale, str):
            raise HTTPException(status_code=400, detail="\"locale\" must be str")
        if modules is not None and not isinstance(modules, list):
            raise HTTPException(status_code=400, detail="\"modules\" must be list")
        if custom_admins is not None and not isinstance(custom_admins, list):
            raise HTTPException(status_code=400, detail="\"custom_admins\" must be list")
        if banned_users is not None and not isinstance(banned_users, list):
            raise HTTPException(status_code=400, detail="\"banned_users\" must be list")
        if target_data is not None and not isinstance(target_data, dict):
            raise HTTPException(status_code=400, detail="\"target_data\" must be dict")

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

        Logger.info(f"[WebUI] {ip} has edited the session data: {target_id}")
        return Response(status_code=204)
    except HTTPException as e:
        raise e
    except Exception:
        Logger.exception()
        raise HTTPException(status_code=400, detail="Bad request")


@app.delete("/api/target/{target_id}")
async def delete_target_info(request: Request, target_id: str):
    ip = request.client.host
    try:
        verify_jwt(request)

        target_info = await TargetInfo.get_by_target_id(target_id, create=False)
        if target_info:
            await target_info.delete()

        Logger.info(f"[WebUI] {ip} has deleted the session data: {target_id}")
        return Response(status_code=204)
    except HTTPException as e:
        raise e
    except Exception:
        Logger.exception()
        raise HTTPException(status_code=400, detail="Bad request")


@app.get("/api/sender")
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
            "sender_list": results,
            "total": total
        }
    except HTTPException as e:
        raise e
    except Exception:
        Logger.exception()
        raise HTTPException(status_code=400, detail="Bad request")


@app.get("/api/sender/{sender_id}")
async def get_sender_info(request: Request, sender_id: str):
    try:
        verify_jwt(request)
        sender_info = await SenderInfo.get_by_sender_id(sender_id, create=False)
        if not sender_info:
            raise HTTPException(status_code=404, detail="Not found")
        return {"sender_info": sender_info}
    except HTTPException as e:
        raise e
    except Exception:
        Logger.exception()
        raise HTTPException(status_code=400, detail="Bad request")


@app.patch("/api/sender/{sender_id}")
async def edit_sender_info(request: Request, sender_id: str):
    ip = request.client.host
    try:
        verify_jwt(request)

        sender_info = await SenderInfo.get_by_sender_id(sender_id)
        body = await request.json()
        superuser = body.get("superuser")
        trusted = body.get("trusted")
        blocked = body.get("blocked")
        warns = body.get("warns")
        petal = body.get("petal")
        sender_data = body.get("sender_data")

        if superuser is not None and not isinstance(superuser, bool):
            raise HTTPException(status_code=400, detail="\"superuser\" must be bool")
        if trusted is not None and not isinstance(trusted, bool):
            raise HTTPException(status_code=400, detail="\"trusted\" must be bool")
        if blocked is not None and not isinstance(blocked, bool):
            raise HTTPException(status_code=400, detail="\"blocked\" must be bool")
        if warns is not None and not isinstance(warns, int):
            raise HTTPException(status_code=400, detail="\"warns\" must be int")
        if petal is not None and not isinstance(petal, int):
            raise HTTPException(status_code=400, detail="\"petal\" must be int")
        if sender_data is not None and not isinstance(sender_data, dict):
            raise HTTPException(status_code=400, detail="\"sender_data\" must be dict")

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

        Logger.info(f"[WebUI] {ip} has edited the user data: {sender_id}")
        return Response(status_code=204)
    except HTTPException as e:
        raise e
    except Exception:
        Logger.exception()
        raise HTTPException(status_code=400, detail="Bad request")


@app.delete("/api/sender/{sender_id}")
async def delete_sender_info(request: Request, sender_id: str):
    ip = request.client.host
    try:
        verify_jwt(request)

        sender_info = await SenderInfo.get_by_sender_id(sender_id, create=False)
        if sender_info:
            await sender_info.delete()
        Logger.info(f"[WebUI] {ip} has deleted the user data: {sender_id}")
        return Response(status_code=204)
    except HTTPException as e:
        raise e
    except Exception:
        Logger.exception()
        raise HTTPException(status_code=400, detail="Bad request")


@app.get("/api/modules_list")
async def get_modules_list(request: Request):
    try:
        verify_jwt(request)
        modules_list = await JobQueueClient.get_modules_list()
        return {"modules": modules_list}
    except HTTPException as e:
        raise e
    except Exception:
        Logger.exception()
        raise HTTPException(status_code=400, detail="Bad request")


@app.get("/api/modules")
async def get_modules_info(request: Request, locale: str = Query(default_locale)):
    try:
        verify_jwt(request)
        modules = await JobQueueClient.get_modules_info(locale=locale)

        return {"modules": modules}
    except HTTPException as e:
        raise e
    except Exception:
        Logger.exception()
        raise HTTPException(status_code=400, detail="Bad request")


@app.get("/api/module/{module_name}/related")
async def search_related_module(request: Request, module_name: str):
    try:
        verify_jwt(request)
        modules = await JobQueueClient.get_module_related(module=module_name)
        return {"modules": modules}
    except HTTPException as e:
        raise e
    except Exception:
        Logger.exception()
        raise HTTPException(status_code=400, detail="Bad request")


@app.get("/api/module/{module_name}/helpdoc")
async def get_module_helpdoc(request: Request, module_name: str, locale: str = Query(default_locale)):
    try:
        verify_jwt(request)
        help_doc = await JobQueueClient.get_module_helpdoc(module=module_name, locale=locale)
        if not help_doc:
            raise HTTPException(status_code=404, detail="Not found")
        return help_doc
    except HTTPException as e:
        raise e
    except Exception:
        Logger.exception()
        raise HTTPException(status_code=400, detail="Bad request")


@app.post("/api/module/{module_name}/reload")
async def reload_module(request: Request, module_name: str):
    ip = request.client.host
    try:
        verify_jwt(request)
        status = await JobQueueClient.post_module_action(module=module_name, action="reload")
        if not status:
            Logger.warning(f"[WebUI] {ip} failed to reload module: {module_name}")
            raise HTTPException(status_code=422, detail="Reload modules failed")
        Logger.info(f"[WebUI] {ip} has reloaded the module: {module_name}")
        return Response(status_code=204)
    except HTTPException as e:
        raise e
    except Exception:
        Logger.exception()
        raise HTTPException(status_code=400, detail="Bad request")


@app.post("/api/module/{module_name}/load")
async def load_module(request: Request, module_name: str):
    ip = request.client.host
    try:
        verify_jwt(request)
        status = await JobQueueClient.post_module_action(module=module_name, action="load")
        if not status:
            Logger.warning(f"[WebUI] {ip} failed to load module: {module_name}")
            raise HTTPException(status_code=422, detail="Load modules failed")
        Logger.info(f"[WebUI] {ip} has loaded the module: {module_name}")
        return Response(status_code=204)

    except HTTPException as e:
        raise e
    except Exception:
        Logger.exception()
        raise HTTPException(status_code=400, detail="Bad request")


@app.post("/api/module/{module_name}/unload")
async def unload_module(request: Request, module_name: str):
    ip = request.client.host
    try:
        verify_jwt(request)
        status = await JobQueueClient.post_module_action(module=module_name, action="unload")
        if not status:
            Logger.warning(f"[WebUI] {ip} failed to unload module: {module_name}")
            raise HTTPException(status_code=422, detail="Unload modules failed")
        Logger.info(f"[WebUI] {ip} has unloaded the module: {module_name}")
        return Response(status_code=204)
    except HTTPException as e:
        raise e
    except Exception:
        Logger.exception()
        raise HTTPException(status_code=400, detail="Bad request")


async def restart():
    await asyncio.sleep(1)
    os._exit(233)


@app.post("/api/restart")
async def restart_bot(request: Request):
    ip = request.client.host
    verify_jwt(request)
    Logger.info(f"[WebUI] {ip} restarted bot.")
    asyncio.create_task(restart())
    return Response(status_code=202)
