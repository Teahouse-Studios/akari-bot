from collections import defaultdict
from datetime import datetime, timedelta, UTC

import jwt
import orjson
from fastapi import HTTPException, Request
from fastapi.responses import Response
from jwt.exceptions import ExpiredSignatureError

from bots.web.client import app, limiter, ph, jwt_secret
from core.config import Config
from core.constants.path import assets_path
from core.database.models import MaliciousLoginRecords
from core.logger import Logger

PASSWORD_PATH = assets_path / "private" / "web" / ".password"
LOGIN_BLOCK_DURATION = 3600

login_failed_attempts = defaultdict(list)
login_max_attempt = Config("login_max_attempt", default=5, table_name="bot_web")


def verify_jwt(request: Request):
    auth = request.headers.get('authorization')
    if not auth or not auth[:7] == "Bearer ":
        raise HTTPException(status_code=401)
    auth_token = auth[7:]

    try:
        payload = jwt.decode(auth_token, jwt_secret, algorithms=["HS256"])
        if PASSWORD_PATH.exists():
            with open(PASSWORD_PATH, "rb") as f:
                last_updated = orjson.loads(f.read()).get("last_updated")

            if last_updated and payload["iat"] < last_updated:
                raise ExpiredSignatureError

        return {"payload": payload}

    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid token")


@app.get("/api/verify")
@limiter.limit("10/second")
async def verify_token(request: Request):
    return verify_jwt(request)


@app.post("/api/login")
async def auth(request: Request):
    ip = request.client.host
    if await MaliciousLoginRecords.check_blocked(ip):
        raise HTTPException(status_code=429, detail="This IP has been blocked")

    try:
        if not PASSWORD_PATH.exists():
            payload = {
                "exp": datetime.now(UTC) + timedelta(hours=24),  # 过期时间
                "iat": datetime.now(UTC),  # 签发时间
                "iss": "auth-api"  # 签发者
            }
            jwt_token = jwt.encode(payload, jwt_secret, algorithm="HS256")

            Logger.info(f"[WebUI] {ip} login successfully.")
            return {"data": jwt_token}

        body = await request.json()
        password = body.get("password", "")

        if len(password) == 0:
            raise HTTPException(status_code=401, detail="Require password")

        with open(PASSWORD_PATH, "rb") as file:
            password_data = orjson.loads(file.read())

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
                Logger.warning(f"[WebUI] {ip} has been blocked due to excessive login failures.")
                raise HTTPException(status_code=429, detail="This IP has been blocked")

            Logger.warning(f"[WebUI] {ip} login failed.")
            raise HTTPException(status_code=403, detail="Invalid password")

        login_failed_attempts.pop(ip, None)

        payload = {
            "exp": datetime.now(UTC) + timedelta(hours=24),
            "iat": datetime.now(UTC),
            "iss": "auth-api"
        }
        jwt_token = jwt.encode(payload, jwt_secret, algorithm="HS256")

        Logger.info(f"[WebUI] {ip} login successfully.")
        return {"data": jwt_token}

    except HTTPException as e:
        raise e
    except Exception:
        Logger.exception()
        raise HTTPException(status_code=400, detail="Bad request")


@app.put("/api/password")
async def change_password(request: Request, response: Response):
    ip = request.client.host
    try:
        verify_jwt(request)

        body = await request.json()
        new_password = body.get("new_password", "")
        password = body.get("password", "")

        if not PASSWORD_PATH.exists():
            if new_password == "":
                raise HTTPException(status_code=400, detail="New password required")

            PASSWORD_PATH.parent.mkdir(parents=True, exist_ok=True)

            password_data = {
                "password": ph.hash(new_password),
                "last_updated": datetime.now().timestamp()
            }
            with open(PASSWORD_PATH, "wb") as file:
                file.write(orjson.dumps(password_data))
            response.delete_cookie("deviceToken")
            return Response(status_code=205)

        with open(PASSWORD_PATH, "rb") as file:
            password_data = orjson.loads(file.read())

        try:
            ph.verify(password_data.get("password", ""), password)
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid password")

        password_data["password"] = ph.hash(new_password)
        password_data["last_updated"] = datetime.now().timestamp()

        with open(PASSWORD_PATH, "wb") as file:
            file.write(orjson.dumps(password_data))

        # TODO 签的jwt存db, 改密码时删掉
        Logger.info(f"[WebUI] {ip} has changed password.")
        return Response(status_code=205)
    except HTTPException as e:
        raise e
    except Exception:
        Logger.exception()
        raise HTTPException(status_code=400, detail="Bad request")


@app.delete("/api/password")
async def clear_password(request: Request):
    ip = request.client.host
    try:
        verify_jwt(request)

        body = await request.json()
        password = body.get("password", "")

        if not PASSWORD_PATH.exists():
            raise HTTPException(status_code=404, detail="Password not set")

        with open(PASSWORD_PATH, "rb") as file:
            password_data = orjson.loads(file.read())

        try:
            ph.verify(password_data.get("password", ""), password)
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid password")

        PASSWORD_PATH.unlink()
        Logger.info(f"[WebUI] {ip} has deleted password.")
        return Response(status_code=205)
    except HTTPException as e:
        raise e
    except Exception:
        Logger.exception()
        raise HTTPException(status_code=400, detail="Bad request")


@app.get("/api/password")
@limiter.limit("10/minute")
async def has_password(request: Request):
    return {"have_password": PASSWORD_PATH.exists()}
