import asyncio
import os
import platform
from datetime import datetime, timedelta, UTC

import psutil
from cpuinfo import get_cpu_info
from fastapi import HTTPException, Request, Query
from fastapi.responses import Response
from tortoise.expressions import Q

from bots.web.client import app, limiter, enable_https, get_client_ip
from core.builtins.utils import command_prefix
from bots.web.config import WebConfig
from core.config.base import BaseConfig, CoreConfig
from core.constants import config_filename
from core.constants.path import config_path
from core.database.models import AnalyticsData, SenderUnionInfo, SenderUnionBind, TargetUnionInfo, TargetUnionBind
from core.logger import Logger
from core.queue.client import JobQueueClient
from .auth import verify_jwt

started_time = datetime.now()


default_locale = BaseConfig.default_locale


async def filter_by_bound_id(bind_model, prefix: str | None, id: str | None) -> Q | None:
    """
    把按平台 ID 的筛选条件转换为对 union 的筛选条件。

    数据现在挂在 union 上，平台 ID 只存在于映射表中，因此需要先查映射表再按 union 过滤。

    :param bind_model: 映射表模型。
    :param prefix: 平台前缀。
    :param id: 平台 ID 的部分内容。
    :return: 针对 union 的筛选条件，无需筛选时为 None。
    """
    if not prefix and not id:
        return None
    id_field = bind_model._meta.pk_attr
    bind_filters = Q()
    if prefix:
        bind_filters &= Q(**{f"{id_field}__startswith": f"{prefix}|"})
    if id:
        bind_filters &= Q(**{f"{id_field}__icontains": id})
    union_ids = await bind_model.filter(bind_filters).values_list("union_id", flat=True)
    return Q(union_id__in=list(set(union_ids)))


async def map_bound_ids(bind_model, union_ids: list[str]) -> dict[str, list[str]]:
    """
    批量获取每个 union 下绑定的全部平台 ID。

    :param bind_model: 映射表模型。
    :param union_ids: union ID 列表。
    """
    id_field = bind_model._meta.pk_attr
    mapping = {u: [] for u in union_ids}
    if not union_ids:
        return mapping
    for row in await bind_model.filter(union_id__in=union_ids).values(id_field, "union_id"):
        mapping.setdefault(row["union_id"], []).append(row[id_field])
    return mapping


def pick_display_id(union_id: str, bound_ids: list[str], prefix: str | None = None) -> str:
    """
    从 union 下的平台 ID 中挑一个用于展示，尽量与筛选前缀一致。
    """
    if prefix:
        for i in bound_ids:
            if i.startswith(f"{prefix}|"):
                return i
    return bound_ids[0] if bound_ids else union_id


def dump_target(target: TargetUnionInfo, bound_ids: list[str], display_id: str) -> dict:
    """
    序列化场景信息。``target_id`` 保持向后兼容，另附 union ID 与全部已绑定的平台 ID。
    """
    return {
        "target_id": display_id,
        "union_id": target.union_id,
        "bound_ids": bound_ids,
        "blocked": target.blocked,
        "muted": target.muted,
        "locale": target.locale,
        "modules": target.modules,
        "custom_admins": target.custom_admins,
        "banned_users": target.banned_users,
        "target_data": target.target_data,
    }


def dump_sender(sender: SenderUnionInfo, bound_ids: list[str], display_id: str) -> dict:
    """
    序列化用户信息。``sender_id`` 保持向后兼容，另附 union ID 与全部已绑定的平台 ID。
    """
    return {
        "sender_id": display_id,
        "union_id": sender.union_id,
        "bound_ids": bound_ids,
        "blocked": sender.blocked,
        "trusted": sender.trusted,
        "superuser": sender.superuser,
        "warns": sender.warns,
        "petal": sender.petal,
        "sender_data": sender.sender_data,
    }


async def resolve_sender_unions(ids: list[str]) -> list[str]:
    """
    把权限列表中的平台账号 ID 解析为 union ID，已经是 union ID 的原样保留。

    ``custom_admins`` / ``banned_users`` 存的是 union ID，但控制台可能直接填入平台账号 ID。
    """
    resolved = []
    for i in ids:
        bind = await SenderUnionBind.get_or_none(sender_id=i)
        resolved.append(bind.union_id if bind else i)
    return list(dict.fromkeys(resolved))


@app.get("/api")
@limiter.limit("10/second")
async def api_root(request: Request):
    return {"message": "Hello, AkariBot!"}


@app.get("/api/init")
@limiter.limit("10/second")
async def get_config(request: Request):
    return {
        "enable_https": enable_https,
        "command_prefix": command_prefix[0],
        "help_url": CoreConfig.help_url,
        "locale": BaseConfig.default_locale,
        "heartbeat_interval": WebConfig.heartbeat_interval,
        "heartbeat_timeout": WebConfig.heartbeat_timeout,
        "heartbeat_attempt": WebConfig.heartbeat_attempt,
    }


@app.get("/api/server-info")
async def server_info(request: Request):
    verify_jwt(request)
    return {
        "os": {
            "system": platform.system(),
            "version": platform.version(),
            "machine": platform.machine(),
            "boot_time": psutil.boot_time(),
        },
        "bot": {
            "started_time": started_time.timestamp(),
            "python_version": platform.python_version(),
            "version": await JobQueueClient.get_bot_version(),
            "web_render_status": await JobQueueClient.get_web_render_status(),
        },
        "cpu": {"cpu_brand": get_cpu_info()["brand_raw"], "cpu_percent": psutil.cpu_percent(interval=1)},
        "memory": {
            "total": psutil.virtual_memory().total / (1024 * 1024),
            "used": psutil.virtual_memory().used / (1024 * 1024),
            "percent": psutil.virtual_memory().percent,
        },
        "disk": {
            "total": psutil.disk_usage("/").total / (1024 * 1024 * 1024),
            "used": psutil.disk_usage("/").used / (1024 * 1024 * 1024),
            "percent": psutil.disk_usage("/").percent,
        },
    }


@app.get("/api/analytics")
async def get_analytics(request: Request, days: int = Query(1)):
    verify_jwt(request)
    try:
        # 时间窗口须以带时区的 datetime 传入：AnalyticsData.timestamp 是 DatetimeField，
        # 传 Unix 时间戳会被原样绑定成数字与日期时间比较，任何记录都落不进区间；
        # 传不带时区的本地时间则会被当作 UTC 处理，窗口整体偏移一个时区差。
        now = datetime.now(UTC)
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
    ip = get_client_ip(request)
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
    size: int = Query(20, gt=0, le=100),
):
    try:
        verify_jwt(request)

        query = TargetUnionInfo.all()
        filters = Q()
        if status == "muted":
            filters &= Q(muted=True)
        if status == "blocked":
            filters &= Q(blocked=True)
        bound_filters = await filter_by_bound_id(TargetUnionBind, prefix, id)
        if bound_filters:
            filters &= bound_filters

        query = query.filter(filters)
        total = await query.count()
        results = await query.offset((page - 1) * size).limit(size)

        bound_map = await map_bound_ids(TargetUnionBind, [t.union_id for t in results])
        target_list = [
            dump_target(
                t, bound_map.get(t.union_id, []), pick_display_id(t.union_id, bound_map.get(t.union_id, []), prefix)
            )
            for t in results
        ]

        return {"target_list": target_list, "total": total}
    except HTTPException as e:
        raise e
    except Exception:
        Logger.exception()
        raise HTTPException(status_code=400, detail="Bad request")


@app.get("/api/target/{target_id}")
async def get_target_info(request: Request, target_id: str):
    try:
        verify_jwt(request)
        target_union_info = await TargetUnionInfo.get_by_target_id(target_id, create=False)
        if not target_union_info:
            raise HTTPException(status_code=404, detail="Not found")
        bound_ids = await target_union_info.list_bound_ids()
        return {"target_info": dump_target(target_union_info, bound_ids, target_id)}
    except HTTPException as e:
        raise e
    except Exception:
        Logger.exception()
        raise HTTPException(status_code=400, detail="Bad request")


@app.patch("/api/target/{target_id}")
async def edit_target_info(request: Request, target_id: str):
    ip = get_client_ip(request)
    try:
        verify_jwt(request)

        target_union_info = await TargetUnionInfo.get_by_target_id(target_id)
        body = await request.json()
        muted = body.get("muted")
        locale = body.get("locale")
        blocked = body.get("blocked")
        modules = body.get("modules")
        custom_admins = body.get("custom_admins")
        banned_users = body.get("banned_users")
        target_data = body.get("target_data")

        if blocked is not None and not isinstance(blocked, bool):
            raise HTTPException(status_code=400, detail='"blocked" must be bool')
        if muted is not None and not isinstance(muted, bool):
            raise HTTPException(status_code=400, detail='"muted" must be bool')
        if locale is not None and not isinstance(locale, str):
            raise HTTPException(status_code=400, detail='"locale" must be str')
        if modules is not None and not isinstance(modules, list):
            raise HTTPException(status_code=400, detail='"modules" must be list')
        if custom_admins is not None and not isinstance(custom_admins, list):
            raise HTTPException(status_code=400, detail='"custom_admins" must be list')
        if banned_users is not None and not isinstance(banned_users, list):
            raise HTTPException(status_code=400, detail='"banned_users" must be list')
        if target_data is not None and not isinstance(target_data, dict):
            raise HTTPException(status_code=400, detail='"target_data" must be dict')

        if muted is not None:
            target_union_info.muted = muted
        if locale is not None:
            target_union_info.locale = locale
        if modules is not None:
            target_union_info.modules = modules
        # 权限名单存的是 union ID，控制台可能直接填平台账号 ID，这里统一解析一遍。
        if custom_admins is not None:
            target_union_info.custom_admins = await resolve_sender_unions(custom_admins)
        if banned_users is not None:
            target_union_info.banned_users = await resolve_sender_unions(banned_users)
        if target_data is not None:
            target_union_info.target_data = target_data
        await target_union_info.save()
        if blocked is not None:
            await target_union_info.edit_attr("blocked", blocked)

        Logger.info(f"[WebUI] {ip} has edited the session data: {target_id}")
        return Response(status_code=204)
    except HTTPException as e:
        raise e
    except Exception:
        Logger.exception()
        raise HTTPException(status_code=400, detail="Bad request")


@app.delete("/api/target/{target_id}")
async def delete_target_info(request: Request, target_id: str):
    ip = get_client_ip(request)
    try:
        verify_jwt(request)

        target_union_info = await TargetUnionInfo.get_by_target_id(target_id, create=False)
        if target_union_info:
            # 删除 union 的同时清掉其下全部映射，否则残留映射会指向不存在的 union。
            await TargetUnionBind.filter(union_id=target_union_info.union_id).delete()
            await target_union_info.delete()

        Logger.info(f"[WebUI] {ip} has deleted the session data: {target_id}")
        return Response(status_code=204)
    except HTTPException as e:
        raise e
    except Exception:
        Logger.exception()
        raise HTTPException(status_code=400, detail="Bad request")


@app.get("/api/sender")
async def get_sender_list(
    request: Request,
    prefix: str = Query(None),
    status: str = Query(None, pattern=r"^(superuser|trusted|blocked)?$"),
    id: str = Query(None),
    page: int = Query(1, gt=0),
    size: int = Query(20, gt=0, le=100),
):
    try:
        verify_jwt(request)

        query = SenderUnionInfo.all()
        filters = Q()
        if status == "superuser":
            filters &= Q(superuser=True)
        elif status == "trusted":
            filters &= Q(trusted=True)
        elif status == "blocked":
            filters &= Q(blocked=True)
        bound_filters = await filter_by_bound_id(SenderUnionBind, prefix, id)
        if bound_filters:
            filters &= bound_filters

        query = query.filter(filters)
        total = await query.count()
        results = await query.offset((page - 1) * size).limit(size)

        bound_map = await map_bound_ids(SenderUnionBind, [s.union_id for s in results])
        sender_list = [
            dump_sender(
                s, bound_map.get(s.union_id, []), pick_display_id(s.union_id, bound_map.get(s.union_id, []), prefix)
            )
            for s in results
        ]

        return {"sender_list": sender_list, "total": total}
    except HTTPException as e:
        raise e
    except Exception:
        Logger.exception()
        raise HTTPException(status_code=400, detail="Bad request")


@app.get("/api/sender/{sender_id}")
async def get_sender_info(request: Request, sender_id: str):
    try:
        verify_jwt(request)
        sender_union_info = await SenderUnionInfo.get_by_sender_id(sender_id, create=False)
        if not sender_union_info:
            raise HTTPException(status_code=404, detail="Not found")
        bound_ids = await sender_union_info.list_bound_ids()
        return {"sender_info": dump_sender(sender_union_info, bound_ids, sender_id)}
    except HTTPException as e:
        raise e
    except Exception:
        Logger.exception()
        raise HTTPException(status_code=400, detail="Bad request")


@app.patch("/api/sender/{sender_id}")
async def edit_sender_info(request: Request, sender_id: str):
    ip = get_client_ip(request)
    try:
        verify_jwt(request)

        sender_union_info = await SenderUnionInfo.get_by_sender_id(sender_id)
        body = await request.json()
        superuser = body.get("superuser")
        trusted = body.get("trusted")
        blocked = body.get("blocked")
        warns = body.get("warns")
        petal = body.get("petal")
        sender_data = body.get("sender_data")

        if superuser is not None and not isinstance(superuser, bool):
            raise HTTPException(status_code=400, detail='"superuser" must be bool')
        if trusted is not None and not isinstance(trusted, bool):
            raise HTTPException(status_code=400, detail='"trusted" must be bool')
        if blocked is not None and not isinstance(blocked, bool):
            raise HTTPException(status_code=400, detail='"blocked" must be bool')
        if warns is not None and not isinstance(warns, int):
            raise HTTPException(status_code=400, detail='"warns" must be int')
        if petal is not None and not isinstance(petal, int):
            raise HTTPException(status_code=400, detail='"petal" must be int')
        if sender_data is not None and not isinstance(sender_data, dict):
            raise HTTPException(status_code=400, detail='"sender_data" must be dict')

        if superuser is not None:
            sender_union_info.superuser = superuser
        if trusted is not None:
            sender_union_info.trusted = trusted
        if warns is not None:
            sender_union_info.warns = warns
        if petal is not None:
            sender_union_info.petal = petal
        if sender_data is not None:
            sender_union_info.sender_data = sender_data
        await sender_union_info.save()
        if blocked is not None:
            await sender_union_info.edit_attr("blocked", blocked)

        Logger.info(f"[WebUI] {ip} has edited the user data: {sender_id}")
        return Response(status_code=204)
    except HTTPException as e:
        raise e
    except Exception:
        Logger.exception()
        raise HTTPException(status_code=400, detail="Bad request")


@app.delete("/api/sender/{sender_id}")
async def delete_sender_info(request: Request, sender_id: str):
    ip = get_client_ip(request)
    try:
        verify_jwt(request)

        sender_union_info = await SenderUnionInfo.get_by_sender_id(sender_id, create=False)
        if sender_union_info:
            # 删除 union 的同时清掉其下全部映射，否则残留映射会指向不存在的 union。
            await SenderUnionBind.filter(union_id=sender_union_info.union_id).delete()
            await sender_union_info.delete()
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
    ip = get_client_ip(request)
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
    ip = get_client_ip(request)
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
    ip = get_client_ip(request)
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
    ip = get_client_ip(request)
    verify_jwt(request)
    Logger.info(f"[WebUI] {ip} restarted bot.")
    asyncio.create_task(restart())
    return Response(status_code=202)
