"""TapTap 扫码登录与 Phigros SessionToken 换取。"""

from base64 import b64encode
from dataclasses import dataclass
from hashlib import md5, sha1, sha256
from hmac import new as new_hmac
from json import dumps
from pathlib import Path
from secrets import token_urlsafe
from time import time
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
import qrcode

from core.utils.cache import random_cache_path
from core.utils.http import proxy

from .PhiCloudActionAsync.ActionLib import DEFAULT_TIMEOUT

APP_KEY = "Qr9AEqtuoSVS3zeD6iVbM4ZC0AtkJcQ89tywVyi0"
CLIENT_ID = "rAK3FfdieFob2Nn8Am"
CLOUD_SERVER_ADDRESS = "https://rak3ffdi.cloud.tds1.tapapis.cn"
CHINA_WEB_HOST = "https://accounts.tapapis.cn"
CHINA_API_HOST = "https://open.tapapis.cn"
DEVICE_CODE_URL = f"{CHINA_WEB_HOST}/oauth2/v1/device/code"
TOKEN_URL = f"{CHINA_WEB_HOST}/oauth2/v1/token"
PROFILE_URL = f"{CHINA_API_HOST}/account/profile/v1?client_id={CLIENT_ID}"
TAP_SDK_VERSION = "2.1"


class TapTapLoginError(Exception):
    """TapTap 登录流程失败。"""


class TapTapAuthorizationDenied(TapTapLoginError):
    """用户拒绝或取消了 TapTap 授权。"""


class TapTapQRCodeExpired(TapTapLoginError):
    """TapTap 设备码已经过期。"""


class TapTapSlowDown(TapTapLoginError):
    """TapTap 要求降低设备码轮询频率。"""


@dataclass(frozen=True)
class TapTapQRCode:
    """一次 TapTap 设备码授权所需的数据。"""

    device_id: str
    device_code: str
    qrcode_url: str
    expires_in: int
    interval: int


def build_client() -> httpx.AsyncClient:
    """构造使用项目代理设置的 TapTap HTTP 客户端。"""
    return httpx.AsyncClient(follow_redirects=True, timeout=DEFAULT_TIMEOUT, proxy=proxy)


def generate_qrcode(url: str) -> Path:
    """把授权链接生成为缓存目录中的二维码图片。"""
    path = random_cache_path("png")
    qrcode.make(url).save(path)
    return path


def build_mac_authorization(
    access_token: dict[str, Any],
    url: str = PROFILE_URL,
    timestamp: int | None = None,
    nonce: str | None = None,
) -> str:
    """为 TapTap OpenAPI 构造 MAC Authorization 请求头。"""
    timestamp = int(time()) if timestamp is None else timestamp
    nonce = token_urlsafe(12) if nonce is None else nonce
    parsed = urlsplit(url)
    uri = parsed.path + (f"?{parsed.query}" if parsed.query else "")
    normalized = f"{timestamp}\n{nonce}\nGET\n{uri}\n{parsed.hostname}\n{parsed.port or 443}\n\n"

    algorithm = access_token.get("mac_algorithm", "hmac-sha-1").lower()
    if algorithm == "hmac-sha-1":
        digest = sha1
    elif algorithm == "hmac-sha-256":
        digest = sha256
    else:
        raise TapTapLoginError(f"Unsupported MAC algorithm: {algorithm}")

    mac = b64encode(new_hmac(access_token["mac_key"].encode(), normalized.encode(), digest).digest()).decode()
    return f'MAC id="{access_token["kid"]}",ts="{timestamp}",nonce="{nonce}",mac="{mac}"'


def _response_payload(response: httpx.Response) -> dict[str, Any]:
    """读取 JSON 响应，并将非对象结果统一视作登录错误。"""
    try:
        payload = response.json()
    except ValueError as e:
        response.raise_for_status()
        raise TapTapLoginError("TapTap returned an invalid JSON response.") from e
    if not isinstance(payload, dict):
        raise TapTapLoginError("TapTap returned an invalid response payload.")
    return payload


def _response_data(response: httpx.Response) -> dict[str, Any]:
    """读取 TapTap 标准响应中的 data 对象。"""
    payload = _response_payload(response)
    response.raise_for_status()
    data = payload.get("data")
    if not isinstance(data, dict):
        raise TapTapLoginError("TapTap response does not contain a data object.")
    return data


class TapTapLogin:
    """使用已有异步客户端执行 TapTap 设备码登录。"""

    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def request_login_qrcode(self) -> TapTapQRCode:
        """申请一个 TapTap 设备码及二维码地址。"""
        device_id = uuid4().hex
        response = await self.client.post(
            DEVICE_CODE_URL,
            data={
                "client_id": CLIENT_ID,
                "response_type": "device_code",
                "scope": "public_profile",
                "version": TAP_SDK_VERSION,
                "platform": "unity",
                "info": dumps({"device_id": device_id}),
            },
        )
        data = _response_data(response)
        try:
            return TapTapQRCode(
                device_id=device_id,
                device_code=str(data["device_code"]),
                qrcode_url=str(data["qrcode_url"]),
                expires_in=max(1, int(data["expires_in"])),
                interval=max(1, int(data["interval"])),
            )
        except (KeyError, TypeError, ValueError) as e:
            raise TapTapLoginError("TapTap returned incomplete device-code data.") from e

    async def check_qrcode_result(self, qrcode_data: TapTapQRCode) -> dict[str, Any] | None:
        """轮询设备码；尚未授权时返回 ``None``。"""
        response = await self.client.post(
            TOKEN_URL,
            data={
                "grant_type": "device_token",
                "client_id": CLIENT_ID,
                "secret_type": "hmac-sha-1",
                "code": qrcode_data.device_code,
                "version": "1.0",
                "platform": "unity",
                "info": dumps({"device_id": qrcode_data.device_id}),
            },
        )
        payload = _response_payload(response)
        data = payload.get("data")
        if response.is_success and isinstance(data, dict) and data.get("kid") and data.get("mac_key"):
            return data

        error = data.get("error") if isinstance(data, dict) else payload.get("error")
        if error == "authorization_pending":
            return None
        if error == "slow_down":
            raise TapTapSlowDown
        if error in {"expired_token", "invalid_grant"}:
            raise TapTapQRCodeExpired
        if error in {"access_denied", "authorization_declined"}:
            raise TapTapAuthorizationDenied

        response.raise_for_status()
        raise TapTapLoginError(f"TapTap device authorization failed: {error or 'unknown_error'}")

    async def get_profile(self, access_token: dict[str, Any]) -> dict[str, Any]:
        """读取完成授权的 TapTap 用户公开资料。"""
        response = await self.client.get(
            PROFILE_URL,
            headers={"Authorization": build_mac_authorization(access_token)},
        )
        return _response_data(response)

    async def get_user_data(
        self,
        access_token: dict[str, Any],
        profile: dict[str, Any],
    ) -> dict[str, Any]:
        """使用 TapTap 授权数据登录 Phigros 云服务。"""
        timestamp = int(time() * 1000)
        signature = md5(f"{timestamp}{APP_KEY}".encode(), usedforsecurity=False).hexdigest()
        response = await self.client.post(
            f"{CLOUD_SERVER_ADDRESS}/1.1/users",
            headers={
                "X-LC-Id": CLIENT_ID,
                "X-LC-Sign": f"{signature},{timestamp}",
            },
            json={"authData": {"taptap": {**profile, **access_token}}},
        )
        payload = _response_payload(response)
        response.raise_for_status()
        return payload


class TapTapLoginContext:
    """负责关闭 TapTapLogin 使用的 HTTP 客户端。"""

    def __init__(self):
        self.client = build_client()
        self.login = TapTapLogin(self.client)

    async def __aenter__(self) -> TapTapLogin:
        return self.login

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.client.aclose()


__all__ = [
    "TapTapAuthorizationDenied",
    "TapTapLogin",
    "TapTapLoginContext",
    "TapTapLoginError",
    "TapTapQRCode",
    "TapTapQRCodeExpired",
    "TapTapSlowDown",
    "build_mac_authorization",
    "generate_qrcode",
]
