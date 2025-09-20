import asyncio
import glob
import os
import platform
import re
from collections import defaultdict, deque
from datetime import datetime, timedelta, UTC

import jwt
import orjson as json
import psutil
from cpuinfo import get_cpu_info
from fastapi import HTTPException, Request, Response, Query, WebSocket, WebSocketDisconnect
from jwt.exceptions import ExpiredSignatureError
from tortoise.expressions import Q

from bots.web.client import app, limiter, ph, enable_https, jwt_secret
from core.config import Config
from core.constants import config_filename
from core.constants.path import assets_path, config_path, logs_path
from core.database.models import AnalyticsData, SenderInfo, TargetInfo, MaliciousLoginRecords
from core.logger import Logger
from core.queue.client import JobQueueClient

started_time = datetime.now()

PASSWORD_PATH = os.path.join(assets_path, "private", "web", ".password")

default_locale = Config("default_locale", cfg_type=str)
login_max_attempt = Config("login_max_attempt", default=5, table_name="bot_web")
login_failed_attempts = defaultdict(list)

LOGIN_BLOCK_DURATION = 3600
MAX_LOG_HISTORY = 1024

LOG_HEAD_PATTERN = re.compile(
    r"^\[.+\]\[[a-zA-Z0-9\._]+:[a-zA-Z0-9\._]+:\d+\]\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\]\[[A-Z]+\]:")
LOG_TIME_PATTERN = re.compile(r"\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]")


def verify_jwt(request: Request):
    auth = request.headers.get('authorization')
    if not auth or not auth[:7] == "Bearer ":
        raise HTTPException(status_code=401)
    auth_token = auth[7:]

    try:
        payload = jwt.decode(auth_token, jwt_secret, algorithms=["HS256"])
        if os.path.exists(PASSWORD_PATH):
            with open(PASSWORD_PATH, "rb") as f:
                last_updated = json.loads(f.read()).get("last_updated")

            if last_updated and payload["iat"] < last_updated:
                raise ExpiredSignatureError

        return {"payload": payload}

    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid token")


@app.get("/api")
@limiter.limit("2/second")
async def api_root(request: Request):
    return {"message": "Hello, AkariBot!"}


@app.get("/api/init")
@limiter.limit("2/second")
async def get_config(request: Request):
    return {"enable_https": enable_https,
            "locale": Config("default_locale", cfg_type=str),
            "heartbeat_interval": Config("heartbeat_interval", 30, table_name="bot_web"),
            "heartbeat_timeout": Config("heartbeat_timeout", 5, table_name="bot_web"),
            "heartbeat_attempt": Config("heartbeat_attempt", 3, table_name="bot_web")
            }


@app.get("/api/verify")
@limiter.limit("2/second")
async def verify_token(request: Request):
    return verify_jwt(request)


@app.post("/api/login")
async def auth(request: Request, response: Response):
    ip = request.client.host
    if await MaliciousLoginRecords.check_blocked(ip):
        raise HTTPException(status_code=429, detail="This IP has been blocked")

    try:
        if not os.path.exists(PASSWORD_PATH):
            payload = {
                "exp": datetime.now(UTC) + timedelta(hours=24),  # 过期时间
                "iat": datetime.now(UTC),  # 签发时间
                "iss": "auth-api"  # 签发者
            }
            jwt_token = jwt.encode(payload, jwt_secret, algorithm="HS256")

            return {"data": jwt_token}

        body = await request.json()
        password = body.get("password", "")

        if len(password) == 0:
            raise HTTPException(status_code=401, detail="Require password")

        with open(PASSWORD_PATH, "rb") as file:
            password_data = json.loads(file.read())

        try:
            ph.verify(password_data.get("password", ""), password)
        except Exception:
            now = datetime.now(UTC)
            login_failed_attempts[ip] = [t for t in login_failed_attempts[ip] if (now - t).total_seconds() < 600]
            login_failed_attempts[ip].append(now)

            if len(login_failed_attempts[ip]) > login_max_attempt:
                await MaliciousLoginRecords.create(ip_address=ip,
                                                   blocked_until=now + timedelta(seconds=LOGIN_BLOCK_DURATION))
                login_failed_attempts[ip].clear()
                raise HTTPException(status_code=429, detail="This IP has been blocked")

            raise HTTPException(status_code=403, detail="Invalid password")

        login_failed_attempts.pop(ip, None)

        payload = {
            "exp": datetime.now(UTC) + timedelta(hours=24),
            "iat": datetime.now(UTC),
            "iss": "auth-api"
        }
        jwt_token = jwt.encode(payload, jwt_secret, algorithm="HS256")

        return {"data": jwt_token}

    except HTTPException as e:
        raise e
    except Exception:
        Logger.exception()
        raise HTTPException(status_code=400, detail="Bad request")


@app.post("/api/change-password")
@limiter.limit("10/minute")
async def change_password(request: Request, response: Response):
    try:
        verify_jwt(request)

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
            return Response(status_code=205)

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

        # TODO 签的jwt存db, 改密码时删掉
        return Response(status_code=205)
    except HTTPException as e:
        raise e
    except Exception:
        Logger.exception()
        raise HTTPException(status_code=400, detail="Bad request")


@app.post("/api/clear-password")
@limiter.limit("10/minute")
async def clear_password(request: Request, response: Response):
    try:
        verify_jwt(request)

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
        return Response(status_code=205)
    except HTTPException as e:
        raise e
    except Exception:
        Logger.exception()
        raise HTTPException(status_code=400, detail="Bad request")


@app.get("/api/have-password")
@limiter.limit("10/minute")
async def has_password(request: Request):
    return {"data": os.path.exists(PASSWORD_PATH)}


@app.get("/api/server-info")
@limiter.limit("10/minute")
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
        Logger.exception()
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

        return {"cfg_files": cfg_files}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Not found")
    except Exception:
        Logger.exception()
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
        return {"content": content}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Not found")
    except Exception:
        Logger.exception()
        raise HTTPException(status_code=400, detail="Bad request")


@app.post("/api/config/{cfg_filename}/edit")
@limiter.limit("10/minute")
async def edit_config_file(request: Request, cfg_filename: str):
    try:
        verify_jwt(request)

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
        return Response(status_code=204)

    except HTTPException as e:
        raise e
    except Exception:
        Logger.exception()
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
            "target_list": results,
            "total": total
        }
    except HTTPException as e:
        raise e
    except Exception:
        Logger.exception()
        raise HTTPException(status_code=400, detail="Bad request")


@app.get("/api/target/{target_id}")
@limiter.limit("2/second")
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


@app.post("/api/target/{target_id}/edit")
@limiter.limit("10/minute")
async def edit_target_info(request: Request, target_id: str):
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

        return Response(status_code=204)
    except HTTPException as e:
        raise e
    except Exception:
        Logger.exception()
        raise HTTPException(status_code=400, detail="Bad request")


@app.post("/api/target/{target_id}/delete")
@limiter.limit("10/minute")
async def delete_target_info(request: Request, target_id: str):
    try:
        verify_jwt(request)

        target_info = await TargetInfo.get_by_target_id(target_id, create=False)
        if target_info:
            await target_info.delete()

        return Response(status_code=204)
    except HTTPException as e:
        raise e
    except Exception:
        Logger.exception()
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
            "sender_list": results,
            "total": total
        }
    except HTTPException as e:
        raise e
    except Exception:
        Logger.exception()
        raise HTTPException(status_code=400, detail="Bad request")


@app.get("/api/sender/{sender_id}")
@limiter.limit("2/second")
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


@app.post("/api/sender/{sender_id}/edit")
@limiter.limit("10/minute")
async def edit_sender_info(request: Request, sender_id: str):
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

        return Response(status_code=204)
    except HTTPException as e:
        raise e
    except Exception:
        Logger.exception()
        raise HTTPException(status_code=400, detail="Bad request")


@app.post("/api/sender/{sender_id}/delete")
@limiter.limit("10/minute")
async def delete_sender_info(request: Request, sender_id: str):
    try:
        verify_jwt(request)

        sender_info = await SenderInfo.get_by_sender_id(sender_id, create=False)
        if sender_info:
            await sender_info.delete()
        return Response(status_code=204)
    except HTTPException as e:
        raise e
    except Exception:
        Logger.exception()
        raise HTTPException(status_code=400, detail="Bad request")


@app.get("/api/modules_list")
@limiter.limit("2/second")
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
@limiter.limit("2/second")
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
@limiter.limit("10/minute")
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


@app.post("/api/module/{module_name}/reload")
@limiter.limit("10/minute")
async def reload_module(request: Request, module_name: str):
    try:
        verify_jwt(request)
        status = await JobQueueClient.post_module_action(module=module_name, action="reload")
        if not status:
            raise HTTPException(status_code=422, detail="Reload modules failed")
        return Response(status_code=204)
    except HTTPException as e:
        raise e
    except Exception:
        Logger.exception()
        raise HTTPException(status_code=400, detail="Bad request")


@app.post("/api/module/{module_name}/load")
@limiter.limit("10/minute")
async def load_module(request: Request, module_name: str):
    try:
        verify_jwt(request)
        status = await JobQueueClient.post_module_action(module=module_name, action="load")
        if not status:
            raise HTTPException(status_code=422, detail="Load modules failed")

        return Response(status_code=204)

    except HTTPException as e:
        raise e
    except Exception:
        Logger.exception()
        raise HTTPException(status_code=400, detail="Bad request")


@app.post("/api/module/{module_name}/unload")
@limiter.limit("10/minute")
async def unload_module(request: Request, module_name: str):
    try:
        verify_jwt(request)
        status = await JobQueueClient.post_module_action(module=module_name, action="unload")
        if not status:
            raise HTTPException(status_code=422, detail="Unload modules failed")

        return Response(status_code=204)
    except HTTPException as e:
        raise e
    except Exception:
        Logger.exception()
        raise HTTPException(status_code=400, detail="Bad request")


@app.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket):
    await websocket.accept()

    current_date = datetime.today().strftime("%Y-%m-%d")
    last_file_pos = defaultdict(int)  # 日志文件当前位置
    last_file_size = defaultdict(int)  # 日志文件大小
    logs_history = deque(maxlen=MAX_LOG_HISTORY)  # 日志缓存历史
    try:
        while True:
            new_date = datetime.today().strftime("%Y-%m-%d")

            if new_date != current_date:  # 处理跨日期
                last_file_pos.clear()
                last_file_size.clear()
                current_date = new_date

            today_logs = glob.glob(f"{logs_path}/*_{current_date}.log")

            new_loglines = []  # 打包后的日志行
            for log_file in today_logs:
                try:
                    # 比较文件大小，当相同时跳过
                    current_size = os.path.getsize(log_file)
                    if log_file in last_file_size and current_size == last_file_size[log_file]:
                        continue
                    last_file_size[log_file] = current_size

                    if log_file not in last_file_pos:  # 初始化
                        last_file_pos[log_file] = 0

                    with open(log_file, "r", encoding="utf-8") as f:
                        f.seek(last_file_pos[log_file])
                        new_data = f.read()  # 读取新数据
                        last_file_pos[log_file] = f.tell()

                    new_loglines_raw = [line.rstrip() for line in new_data.splitlines() if line.strip()]  # 未打包的新日志行
                except Exception:
                    Logger.exception()
                    continue

                for line in new_loglines_raw:
                    if _log_line_valid(line):  # 日志头
                        new_loglines.append(line)
                    elif new_loglines:
                        last = new_loglines.pop()
                        if isinstance(last, list):  # 添加到多行日志中
                            last.append(line)
                            new_loglines.append(last)
                        elif isinstance(last, str) and _log_line_valid(last):  # 与日志头拼接为多行日志
                            new_loglines.append([last, line])

            if new_loglines:
                new_loglines.sort(
                    key=lambda item: _extract_timestamp(item[0]) if isinstance(item, list) else _extract_timestamp(item)
                )  # 按时间排序

                payload = "\n".join(
                    "\n".join(item) if isinstance(item, list) else item
                    for item in new_loglines
                )
                await websocket.send_text(payload)  # 发送
                logs_history.extend(new_loglines)  # 添加到历史

            await asyncio.sleep(1)

    except WebSocketDisconnect:
        pass
    except Exception:
        Logger.exception()
        await websocket.close()


def _log_line_valid(line: str) -> bool:
    return bool(re.match(LOG_HEAD_PATTERN, line))


def _extract_timestamp(line: str):
    match = LOG_TIME_PATTERN.search(line)
    if match:
        return datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S")
    return None
