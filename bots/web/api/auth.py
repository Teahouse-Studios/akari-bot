import base64
import hashlib
import secrets
import string
from collections import defaultdict
from datetime import datetime, timedelta, UTC

import jwt
import orjson
import pyotp
from cryptography.fernet import Fernet
from fastapi import HTTPException, Request
from fastapi.responses import Response
from jwt.exceptions import ExpiredSignatureError

from bots.web.client import app, limiter, ph, jwt_secret, get_client_ip
from bots.web.config import WebConfig
from core.constants.path import assets_path
from core.database.models import MaliciousLoginRecords
from core.logger import Logger

PASSWORD_PATH = assets_path / "private" / "web" / ".password"
LOGIN_BLOCK_DURATION = 3600


_totp_fernet_key = base64.urlsafe_b64encode(hashlib.sha256(jwt_secret.encode()).digest())
_totp_cipher = Fernet(_totp_fernet_key)

TOTP_ISSUER = "AkariBot"


def _read_password_data() -> dict | None:
    """读取密码文件，不存在时返回 None。"""
    if not PASSWORD_PATH.exists():
        return None
    with open(PASSWORD_PATH, "rb") as f:
        return orjson.loads(f.read())


def _write_password_data(data: dict) -> None:
    """写入密码文件，必要时自动创建父目录。"""
    PASSWORD_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(PASSWORD_PATH, "wb") as f:
        f.write(orjson.dumps(data))


def _is_2fa_enabled(password_data: dict | None) -> bool:
    """检查是否已启用 2FA。"""
    return bool(password_data and password_data.get("totp_enabled") and password_data.get("totp_secret"))


def _get_totp(password_data: dict | None) -> pyotp.TOTP | None:
    """从密码数据中解密并返回 TOTP 实例，失败时返回 None。"""
    if not _is_2fa_enabled(password_data):
        return None
    try:
        decrypted = _totp_cipher.decrypt(password_data["totp_secret"].encode()).decode()
        return pyotp.TOTP(decrypted)
    except Exception:
        Logger.warning("[WebUI] Failed to decrypt TOTP secret")
        return None


def _generate_backup_codes(count: int = 8) -> list[str]:
    codes = []
    for _ in range(count):
        code = "-".join(
            "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(4)) for _ in range(2)
        )
        codes.append(code)
    return codes


def _hash_backup_code(code: str) -> str:
    return hashlib.sha256(code.strip().upper().encode()).hexdigest()


def _verify_backup_code(password_data: dict, code: str) -> bool:
    backup_codes = password_data.get("backup_codes", [])
    if not backup_codes:
        return False
    hashed = _hash_backup_code(code)
    if hashed in backup_codes:
        backup_codes.remove(hashed)
        password_data["backup_codes"] = backup_codes
        return True
    return False


login_failed_attempts = defaultdict(list)
login_max_attempt = WebConfig.login_max_attempt


def verify_jwt(request: Request):
    auth = request.headers.get("authorization")
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
    ip = get_client_ip(request)
    if await MaliciousLoginRecords.check_blocked(ip):
        raise HTTPException(status_code=429, detail="This IP has been blocked")

    try:
        if not PASSWORD_PATH.exists():
            payload = {
                "exp": datetime.now(UTC) + timedelta(hours=24),  # 过期时间
                "iat": datetime.now(UTC),  # 签发时间
                "iss": "auth-api",  # 签发者
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
                await MaliciousLoginRecords.create(
                    ip_address=ip, blocked_until=now + timedelta(seconds=LOGIN_BLOCK_DURATION)
                )
                login_failed_attempts[ip].clear()
                Logger.warning(f"[WebUI] {ip} has been blocked due to excessive login failures.")
                raise HTTPException(status_code=429, detail="This IP has been blocked")

            Logger.warning(f"[WebUI] {ip} login failed.")
            raise HTTPException(status_code=403, detail="Invalid password")

        login_failed_attempts.pop(ip, None)

        if _is_2fa_enabled(password_data):
            totp_code = body.get("totp_code", "")
            backup_code = body.get("backup_code", "")

            if backup_code:
                # 使用 backup code 替代 TOTP 通过 2FA
                if not _verify_backup_code(password_data, backup_code):
                    now = datetime.now(UTC)
                    login_failed_attempts[ip] = [
                        t for t in login_failed_attempts[ip] if (now - t).total_seconds() < 600
                    ]
                    login_failed_attempts[ip].append(now)

                    if len(login_failed_attempts[ip]) > login_max_attempt:
                        await MaliciousLoginRecords.create(
                            ip_address=ip, blocked_until=now + timedelta(seconds=LOGIN_BLOCK_DURATION)
                        )
                        login_failed_attempts[ip].clear()
                        Logger.warning(f"[WebUI] {ip} has been blocked due to excessive login failures.")
                        raise HTTPException(status_code=429, detail="This IP has been blocked")

                    Logger.warning(f"[WebUI] {ip} login failed: invalid backup code.")
                    raise HTTPException(status_code=403, detail="Invalid backup code")
                # 持久化已消耗的 backup code
                _write_password_data(password_data)
            else:
                if not totp_code:
                    raise HTTPException(status_code=401, detail="2FA code required")

                totp = _get_totp(password_data)
                if totp is None or not totp.verify(totp_code, valid_window=1):
                    now = datetime.now(UTC)
                    login_failed_attempts[ip] = [
                        t for t in login_failed_attempts[ip] if (now - t).total_seconds() < 600
                    ]
                    login_failed_attempts[ip].append(now)

                    if len(login_failed_attempts[ip]) > login_max_attempt:
                        await MaliciousLoginRecords.create(
                            ip_address=ip, blocked_until=now + timedelta(seconds=LOGIN_BLOCK_DURATION)
                        )
                        login_failed_attempts[ip].clear()
                        Logger.warning(f"[WebUI] {ip} has been blocked due to excessive login failures.")
                        raise HTTPException(status_code=429, detail="This IP has been blocked")

                    Logger.warning(f"[WebUI] {ip} 2FA verification failed.")
                    raise HTTPException(status_code=403, detail="Invalid 2FA code")

        payload = {"exp": datetime.now(UTC) + timedelta(hours=24), "iat": datetime.now(UTC), "iss": "auth-api"}
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
    ip = get_client_ip(request)
    try:
        verify_jwt(request)

        body = await request.json()
        new_password = body.get("new_password", "")
        password = body.get("password", "")

        if not PASSWORD_PATH.exists():
            if new_password == "":
                raise HTTPException(status_code=400, detail="New password required")

            PASSWORD_PATH.parent.mkdir(parents=True, exist_ok=True)

            password_data = {"password": ph.hash(new_password), "last_updated": datetime.now().timestamp()}
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

        # 2FA 启用时，需要验证 TOTP 码
        if _is_2fa_enabled(password_data):
            totp_code = body.get("totp_code", "")
            backup_code = body.get("backup_code", "")

            if backup_code:
                # 使用 backup code 替代 TOTP 通过 2FA
                if not _verify_backup_code(password_data, backup_code):
                    now = datetime.now(UTC)
                    login_failed_attempts[ip] = [
                        t for t in login_failed_attempts[ip] if (now - t).total_seconds() < 600
                    ]
                    login_failed_attempts[ip].append(now)

                    if len(login_failed_attempts[ip]) > login_max_attempt:
                        await MaliciousLoginRecords.create(
                            ip_address=ip, blocked_until=now + timedelta(seconds=LOGIN_BLOCK_DURATION)
                        )
                        login_failed_attempts[ip].clear()
                        Logger.warning(f"[WebUI] {ip} has been blocked due to excessive login failures.")
                        raise HTTPException(status_code=429, detail="This IP has been blocked")

                    Logger.warning(f"[WebUI] {ip} login failed: invalid backup code.")
                    raise HTTPException(status_code=403, detail="Invalid backup code")
                # 持久化已消耗的 backup code
                _write_password_data(password_data)
            else:
                if not totp_code:
                    raise HTTPException(status_code=400, detail="2FA code required")
                totp = _get_totp(password_data)
                if totp is None or not totp.verify(totp_code, valid_window=1):
                    raise HTTPException(status_code=400, detail="Invalid 2FA code")

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
    ip = get_client_ip(request)
    try:
        verify_jwt(request)

        body = await request.json()
        password = body.get("password", "")

        if not PASSWORD_PATH.exists():
            raise HTTPException(status_code=404, detail="Password not set")

        with open(PASSWORD_PATH, "rb") as file:
            password_data = orjson.loads(file.read())

        # 2FA 启用时不允许清除密码
        if _is_2fa_enabled(password_data):
            raise HTTPException(
                status_code=400, detail="Cannot clear password while 2FA is enabled. Please disable 2FA first."
            )

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


@app.get("/api/totp")
async def get_totp_status(request: Request):
    try:
        verify_jwt(request)
        password_data = _read_password_data()
        return {"enabled": _is_2fa_enabled(password_data)}
    except HTTPException as e:
        raise e
    except Exception:
        Logger.exception()
        raise HTTPException(status_code=400, detail="Bad request")


@app.post("/api/totp/setup")
@limiter.limit("5/minute")
async def setup_totp(request: Request):
    try:
        verify_jwt(request)

        if not PASSWORD_PATH.exists():
            raise HTTPException(status_code=400, detail="Password not set")

        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        uri = totp.provisioning_uri(name="AkariBot", issuer_name=TOTP_ISSUER)

        Logger.info(f"[WebUI] {get_client_ip(request)} requested 2FA setup.")
        return {"secret": secret, "uri": uri}
    except HTTPException as e:
        raise e
    except Exception:
        Logger.exception()
        raise HTTPException(status_code=400, detail="Bad request")


@app.post("/api/totp/enable")
@limiter.limit("5/minute")
async def enable_totp(request: Request):
    ip = get_client_ip(request)
    try:
        verify_jwt(request)

        if not PASSWORD_PATH.exists():
            raise HTTPException(status_code=400, detail="Password not set")

        body = await request.json()
        secret = body.get("secret", "")
        code = body.get("code", "")

        if not secret or not code:
            raise HTTPException(status_code=400, detail="Secret and code are required")

        totp = pyotp.TOTP(secret)
        if not totp.verify(code, valid_window=1):
            Logger.warning(f"[WebUI] {ip} 2FA enable failed: invalid TOTP code.")
            raise HTTPException(status_code=400, detail="Invalid TOTP code")

        password_data = _read_password_data()
        if password_data is None:
            raise HTTPException(status_code=400, detail="Password not set")

        # 加密并存储 TOTP 密钥
        encrypted_secret = _totp_cipher.encrypt(secret.encode()).decode()
        password_data["totp_secret"] = encrypted_secret
        password_data["totp_enabled"] = True

        # 生成并存储 backup codes
        backup_codes = _generate_backup_codes()
        password_data["backup_codes"] = [_hash_backup_code(c) for c in backup_codes]

        _write_password_data(password_data)

        Logger.info(f"[WebUI] {ip} enabled 2FA.")
        return {"message": "success", "backup_codes": backup_codes}
    except HTTPException as e:
        raise e
    except Exception:
        Logger.exception()
        raise HTTPException(status_code=400, detail="Bad request")


@app.post("/api/totp/backup-codes/reset")
@limiter.limit("5/minute")
async def reset_backup_codes(request: Request):
    ip = get_client_ip(request)
    try:
        verify_jwt(request)

        if not PASSWORD_PATH.exists():
            raise HTTPException(status_code=400, detail="Password not set")

        password_data = _read_password_data()
        if password_data is None:
            raise HTTPException(status_code=400, detail="Password not set")

        if not _is_2fa_enabled(password_data):
            raise HTTPException(status_code=400, detail="2FA is not enabled")

        body = await request.json()
        password = body.get("password", "")
        totp_code = body.get("totp_code", "")
        backup_code = body.get("backup_code", "")

        if not password and not (totp_code or backup_code):
            raise HTTPException(status_code=400, detail="Password is required, and provide TOTP code or a backup code")

        # 验证密码
        try:
            ph.verify(password_data.get("password", ""), password)
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid password")

        # 验证 TOTP
        if backup_code:
            if not _verify_backup_code(password_data, backup_code):
                Logger.warning(f"[WebUI] {ip} ecovery codes reset failed: invalid backup code.")
                raise HTTPException(status_code=400, detail="Invalid backup code")
        else:
            totp = _get_totp(password_data)
            if totp is None or not totp.verify(totp_code, valid_window=1):
                Logger.warning(f"[WebUI] {ip} backup codes reset failed: invalid TOTP code.")
                raise HTTPException(status_code=400, detail="Invalid TOTP code")

        # 生成新的 backup codes
        backup_codes = _generate_backup_codes()
        password_data["backup_codes"] = [_hash_backup_code(c) for c in backup_codes]
        _write_password_data(password_data)

        Logger.info(f"[WebUI] {ip} reset backup codes.")
        return {"message": "success", "backup_codes": backup_codes}
    except HTTPException as e:
        raise e
    except Exception:
        Logger.exception()
        raise HTTPException(status_code=400, detail="Bad request")


@app.post("/api/totp/disable")
@limiter.limit("5/minute")
async def disable_totp(request: Request):
    ip = get_client_ip(request)

    try:
        verify_jwt(request)

        body = await request.json()

        password_data = _read_password_data()
        if password_data is None:
            raise HTTPException(status_code=400, detail="Password not set")

        if not _is_2fa_enabled(password_data):
            raise HTTPException(status_code=400, detail="2FA is not enabled")

        password = body.get("password", "")
        totp_code = body.get("totp_code", "")
        backup_code = body.get("backup_code", "")

        if not password and not (totp_code or backup_code):
            raise HTTPException(status_code=400, detail="Password is required, and provide TOTP code or a backup code")

        # 验证密码
        try:
            ph.verify(password_data.get("password", ""), password)
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid password")

        # 验证 TOTP
        if backup_code:
            if not _verify_backup_code(password_data, backup_code):
                Logger.warning(f"[WebUI] {ip} 2FA disable failed: invalid backup code.")
                raise HTTPException(status_code=400, detail="Invalid backup code")
        else:
            totp = _get_totp(password_data)
            if totp is None or not totp.verify(totp_code, valid_window=1):
                Logger.warning(f"[WebUI] {ip} 2FA disable failed: invalid TOTP code.")
                raise HTTPException(status_code=400, detail="Invalid TOTP code")

        # 移除 2FA 数据，保留密码
        password_data.pop("totp_secret", None)
        password_data.pop("totp_enabled", None)
        password_data.pop("backup_codes", None)
        _write_password_data(password_data)

        Logger.info(f"[WebUI] {ip} disabled 2FA.")
        return {"message": "2FA disabled successfully"}
    except HTTPException as e:
        raise e
    except Exception:
        Logger.exception()
        raise HTTPException(status_code=400, detail="Bad request")
