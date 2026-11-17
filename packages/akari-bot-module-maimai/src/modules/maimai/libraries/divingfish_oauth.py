import asyncio
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import orjson

from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import I18NContext, Url
from core.logger import Logger
from core.utils.http import get_url, post_url
from modules.maimai.config import MaimaiConfig, MaimaiSecretConfig
from ..database.models import DivingProberBindInfo

# 授权服务器根地址。各端点路径本应从发现文档读取，此处直接写死以简化实现。
DF_AUTH_SERVER = "https://auth.diving-fish.com"
DF_TOKEN_URL = f"{DF_AUTH_SERVER}/oauth/token"
DF_DEVICE_AUTHORIZATION_URL = f"{DF_AUTH_SERVER}/oauth/device_authorization"
DF_REVOKE_URL = f"{DF_AUTH_SERVER}/oauth/revoke"
DF_DEVICE_VERIFY_URL = f"{DF_AUTH_SERVER}/device"
DF_API_BASE = "https://www.diving-fish.com/api"
DF_MAIMAI_RECORDS_URL = f"{DF_API_BASE}/maimaidxprober/player/records"

DF_CLIENT_ID = MaimaiConfig.diving_fish_client_id
DF_OAUTH_ENABLED = bool(DF_CLIENT_ID)
DF_CLIENT_SECRET = MaimaiSecretConfig.diving_fish_client_secret
# 登记为机密客户端时控制台会另外生成 client_secret，配置里填了它就说明该应用属于这一形态。
DF_CONFIDENTIAL_CLIENT = bool(DF_CLIENT_SECRET)

DF_SCOPE_MAIMAI = "prober.records.read"
DF_SCOPE_CHUNITHM = "chunithm.records.read"
DF_SCOPES = f"{DF_SCOPE_MAIMAI} {DF_SCOPE_CHUNITHM}"

_DEVICE_CODE_GRANT_TYPE = "urn:ietf:params:oauth:grant-type:device_code"
_ON_BEHALF_OF_GRANT_TYPE = "urn:diving-fish:params:oauth:grant-type:on-behalf-of"
_TOKEN_EXPIRE_MARGIN = 30
_SLOW_DOWN_STEP = 5
# 换票所得令牌的有效期比授权码方式的 15 分钟更短，缺失 expires_in 时按此值保守处理。
_ON_BEHALF_OF_TOKEN_TTL = 300.0

_access_token_cache: dict[str, tuple[str, float]] = {}
_refresh_locks: dict[str, asyncio.Lock] = {}


class DivingFishOAuthError(Exception):
    """水鱼 OAuth 流程失败。"""


class DivingFishAuthorizationDenied(DivingFishOAuthError):
    """用户拒绝了本次授权。"""


class DivingFishDeviceCodeExpired(DivingFishOAuthError):
    """设备码已过期，用户未在有效期内完成授权。"""


class DivingFishSlowDown(DivingFishOAuthError):
    """授权服务器要求降低轮询频率。"""


class DivingFishTokenRevoked(DivingFishOAuthError):
    """refresh token 已失效：用户撤销了授权，或令牌链因并发刷新被吊销。"""


class DivingFishConsentRequired(DivingFishTokenRevoked):
    """该用户未授权本应用，换票被拒。"""


class DivingFishRateLimited(DivingFishOAuthError):
    """请求过于频繁，授权服务器要求稍后再试。"""


@dataclass(frozen=True)
class DivingFishDeviceCode:
    device_code: str
    user_code: str
    verification_uri: str
    verification_uri_complete: str
    expires_in: int
    interval: int


def _masked(value: str) -> str:
    if len(value) < 5:
        return "*" * len(value)
    return f"{value[:2]}{'*' * (len(value) - 4)}{value[-2:]}"


def binding_label(session_info) -> str:
    sender = str(session_info.get_common_sender_id())
    client = session_info.client_name or "Bot"
    return f"{client} {_masked(sender)}"


def diving_fish_bind_usable(bind_info: DivingProberBindInfo | None, confidential: bool | None = None) -> bool:
    """判断一条水鱼绑定记录当前是否可用于取分。

    :param bind_info: 该用户的绑定记录。
    :param confidential: 是否按机密客户端判断，默认取配置。
    :return: 是否可用。
    """
    if not bind_info:
        return False
    if confidential is None:
        confidential = DF_CONFIDENTIAL_CLIENT
    if confidential:
        return bool(bind_info.subject)
    return bool(bind_info.refresh_token)


def _authenticated(payload: dict) -> dict:
    if DF_CONFIDENTIAL_CLIENT:
        payload["client_secret"] = DF_CLIENT_SECRET
    return payload


async def _post_form(url: str, payload: dict, *, attempt: int = 3, expect_json: bool = True) -> dict:
    try:
        resp = await post_url(
            url,
            data=urlencode(payload),
            status_code=None,
            headers={"Content-Type": "application/x-www-form-urlencoded", "accept": "application/json"},
            fmt="json" if expect_json else None,
            attempt=attempt,
        )
    except Exception as e:
        raise DivingFishOAuthError(str(e)) from e
    if not expect_json:
        return {}
    if not isinstance(resp, dict):
        raise DivingFishOAuthError(f"Unexpected response: {resp!r}")
    return resp


def _expires_in(resp: dict, default: float = 900.0) -> float:
    try:
        return float(resp.get("expires_in", default))
    except (TypeError, ValueError):
        return default


async def request_device_code(label: str) -> DivingFishDeviceCode:
    resp = await _post_form(
        DF_DEVICE_AUTHORIZATION_URL,
        _authenticated(
            {
                "client_id": DF_CLIENT_ID,
                "scope": DF_SCOPES,
                "binding_label": label,
            }
        ),
    )
    error = resp.get("error")
    if error:
        description = resp.get("error_description", "")
        raise DivingFishOAuthError(f"Device authorization failed: {error} {description}".strip())
    device_code = resp.get("device_code")
    user_code = resp.get("user_code")
    if not device_code or not user_code:
        raise DivingFishOAuthError(f"Device authorization returned no device code: {resp!r}")
    try:
        expires_in = int(resp.get("expires_in", 600))
    except (TypeError, ValueError):
        expires_in = 600
    try:
        interval = int(resp.get("interval", 5))
    except (TypeError, ValueError):
        interval = 5
    return DivingFishDeviceCode(
        device_code=str(device_code),
        user_code=str(user_code),
        verification_uri=str(resp.get("verification_uri") or DF_DEVICE_VERIFY_URL),
        verification_uri_complete=str(resp.get("verification_uri_complete") or DF_DEVICE_VERIFY_URL),
        expires_in=max(1, expires_in),
        interval=max(1, interval),
    )


async def poll_device_token(device_code: str) -> dict | None:
    """轮询一次设备码，尝试取得该用户的令牌。

    :param device_code: 设备码端点返回的设备码。
    :return: 令牌响应；用户尚未完成授权时返回 `None`。
    :raise DivingFishSlowDown: 轮询过快，调用方应延长间隔后继续。
    :raise DivingFishAuthorizationDenied: 用户拒绝授权。
    :raise DivingFishDeviceCodeExpired: 设备码已过期。
    :raise DivingFishOAuthError: 其它错误。
    """
    resp = await _post_form(
        DF_TOKEN_URL,
        _authenticated(
            {
                "grant_type": _DEVICE_CODE_GRANT_TYPE,
                "device_code": device_code,
                "client_id": DF_CLIENT_ID,
            }
        ),
        attempt=1,
    )
    error = resp.get("error")
    if not error:
        if not resp.get("access_token"):
            raise DivingFishOAuthError(f"Device code exchange returned no token: {resp!r}")
        if DF_CONFIDENTIAL_CLIENT:
            # 机密客户端靠换票续期，用不到 refresh token，但必须拿到用户标识。
            if resp.get("sub") is None:
                raise DivingFishOAuthError(f"Device code exchange returned no subject: {resp!r}")
        elif not resp.get("refresh_token"):
            raise DivingFishOAuthError(f"Device code exchange returned no refresh token: {resp!r}")
        return resp
    if error == "authorization_pending":
        return None
    if error == "slow_down":
        raise DivingFishSlowDown(error)
    if error == "access_denied":
        raise DivingFishAuthorizationDenied(error)
    if error == "expired_token":
        raise DivingFishDeviceCodeExpired(error)
    raise DivingFishOAuthError(f"Device code exchange failed: {error}")


async def refresh_access_token(refresh_token: str) -> dict:
    """以 refresh token 换取新的 access token 与 refresh token。

    :param refresh_token: 当前持有的 refresh token。
    :return: 令牌响应，含轮换后的 `refresh_token`。
    :raise DivingFishTokenRevoked: 该 refresh token 已失效，用户需要重新绑定。
    :raise DivingFishOAuthError: 其它刷新错误。
    """
    resp = await _post_form(
        DF_TOKEN_URL,
        _authenticated(
            {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": DF_CLIENT_ID,
            }
        ),
        attempt=1,
    )
    error = resp.get("error")
    if error:
        if error == "invalid_grant":
            raise DivingFishTokenRevoked(f"Refresh token is no longer valid: {resp.get('error_description', '')}")
        raise DivingFishOAuthError(f"Token refresh failed: {error}")
    if not resp.get("access_token"):
        raise DivingFishOAuthError(f"Token refresh returned no access token: {resp!r}")
    return resp


async def exchange_on_behalf_of(subject: str) -> dict:
    """换票：以应用凭据换取一张代表指定用户的短期令牌。

    :param subject: 用户标识，写法为 `sub:<水鱼用户 ID>`。
    :return: 令牌响应，含 `access_token` 与 `expires_in`，不含 refresh token。
    :raise DivingFishConsentRequired: 该用户未授权本应用，需引导其重新绑定。
    :raise DivingFishRateLimited: 换票过于频繁。
    :raise DivingFishOAuthError: 其它换票错误，如客户端凭据有误。
    """
    resp = await _post_form(
        DF_TOKEN_URL,
        _authenticated(
            {
                "grant_type": _ON_BEHALF_OF_GRANT_TYPE,
                "client_id": DF_CLIENT_ID,
                "subject": subject,
            }
        ),
        attempt=1,
    )
    error = resp.get("error")
    if error:
        description = resp.get("error_description", "")
        if error == "consent_required":
            raise DivingFishConsentRequired(f"Consent required: {description}".strip())
        if error == "slow_down":
            raise DivingFishRateLimited(f"429 Slow down: {description}".strip())
        raise DivingFishOAuthError(f"Token exchange failed: {error} {description}".strip())
    if not resp.get("access_token"):
        raise DivingFishOAuthError(f"Token exchange returned no access token: {resp!r}")
    return resp


def _cache_token(union_id: str, token: str, expires_in: float) -> None:
    _access_token_cache[union_id] = (token, time.monotonic() + max(0.0, expires_in - _TOKEN_EXPIRE_MARGIN))


def _cached_access_token(union_id: str) -> str | None:
    cached = _access_token_cache.get(union_id)
    if cached and cached[1] > time.monotonic():
        return cached[0]
    return None


def drop_access_token(union_id: str) -> None:
    """丢弃缓存的 access token，供资源服务器判定令牌失效后重新获取。

    :param union_id: 用户联合 ID。
    """
    _access_token_cache.pop(union_id, None)


async def get_access_token(bind_info: DivingProberBindInfo) -> str:
    """取得代表该绑定用户的 access token，未过期时复用进程内缓存。

    :param bind_info: 该用户的绑定记录。
    :return: access token。
    :raise DivingFishTokenRevoked: 凭据已失效或用户不再授权，用户需要重新绑定。
    :raise DivingFishOAuthError: 其它刷新或换票错误。
    """
    union_id = bind_info.union_id
    cached = _cached_access_token(union_id)
    if cached:
        return cached

    lock = _refresh_locks.setdefault(union_id, asyncio.Lock())
    async with lock:
        # 等待期间可能已有一次取令牌完成，复查缓存以免白白再换一张。
        cached = _cached_access_token(union_id)
        if cached:
            return cached
        if DF_CONFIDENTIAL_CLIENT:
            subject = bind_info.subject
            if not subject:
                # 换票需要用户标识，记录里没有只可能是绑定出自旧流程，重新绑定一次即可补上。
                raise DivingFishTokenRevoked("No Diving-Fish user id stored for this user.")
            resp = await exchange_on_behalf_of(f"sub:{subject}")
            token = str(resp["access_token"])
            _cache_token(union_id, token, _expires_in(resp, _ON_BEHALF_OF_TOKEN_TTL))
            return token
        refresh_token = bind_info.refresh_token
        if not refresh_token:
            raise DivingFishTokenRevoked("No refresh token stored for this user.")
        resp = await refresh_access_token(refresh_token)
        rotated = str(resp.get("refresh_token") or refresh_token)
        subject = resp.get("sub")
        await DivingProberBindInfo.update_refresh_token(
            union_id, rotated, subject=str(subject) if subject is not None else None
        )
        bind_info.refresh_token = rotated
        token = str(resp["access_token"])
        _cache_token(union_id, token, _expires_in(resp))
        return token


async def request_player_data(
    bind_info: DivingProberBindInfo,
    url: str,
    *,
    method: str = "GET",
    data: Any = None,
    params: dict[str, Any] | None = None,
) -> Any:
    """携带代表该用户的 Bearer 令牌请求查分器端点。

    :param bind_info: 该用户的绑定记录。
    :param url: 端点地址。
    :param method: 请求方法，`GET` 或 `POST`。
    :param data: `POST` 请求体，将以 JSON 发送。
    :param params: `GET` 查询参数。
    :return: 响应体解析所得的 JSON。
    """

    async def _send(token: str):
        headers = {
            "Content-Type": "application/json",
            "accept": "*/*",
            "Authorization": f"Bearer {token}",
        }
        if method == "POST":
            return await post_url(url, data=orjson.dumps(data), status_code=200, headers=headers, fmt="json")
        return await get_url(url, status_code=200, params=params, headers=headers, fmt="json")

    token = await get_access_token(bind_info)
    try:
        return await _send(token)
    except Exception as e:
        # 401：令牌无效、已过期，或 Authorization 头格式有误。刷新一次后重试。
        if not str(e).startswith("401"):
            raise
    drop_access_token(bind_info.union_id)
    token = await get_access_token(bind_info)
    return await _send(token)


async def revoke_token(token: str, token_type_hint: str = "refresh_token") -> None:
    await _post_form(
        DF_REVOKE_URL,
        _authenticated(
            {
                "token": token,
                "token_type_hint": token_type_hint,
                "client_id": DF_CLIENT_ID,
            }
        ),
        expect_json=False,
    )


async def fill_bind_username(bind_info: DivingProberBindInfo) -> str:
    """补全绑定记录中的水鱼用户名，并返回昵称。

    :param bind_info: 该用户的绑定记录。
    :return: 昵称；获取失败时返回空字符串。
    :raise DivingFishTokenRevoked: 令牌已失效，用户需要重新绑定。
    """
    try:
        data = await request_player_data(bind_info, DF_MAIMAI_RECORDS_URL)
    except DivingFishTokenRevoked:
        raise
    except Exception:
        Logger.exception()
        return ""
    username = str(data.get("username", ""))
    nickname = str(data.get("nickname", ""))
    if username and username != bind_info.username:
        if not await DivingProberBindInfo.set_bind_info(bind_info.union_id, username=username):
            Logger.warning(f"Failed to store the Diving-Fish username of {bind_info.union_id}.")
        else:
            bind_info.username = username
    return nickname


async def store_binding(union_id: str, token: dict) -> bool:
    """把一次成功的设备码绑定落盘。

    :param union_id: 用户联合 ID。
    :param token: 设备码兑换所得的令牌响应。
    :return: 是否写入成功。
    """
    if DF_CONFIDENTIAL_CLIENT:
        subject = token.get("sub")
        if subject is None:
            Logger.error("The Diving-Fish device code exchange returned no subject.")
            return False
        return await DivingProberBindInfo.set_bind_info(
            union_id=union_id, username="", refresh_token="", subject=str(subject)
        )
    refresh_token = token.get("refresh_token")
    if not refresh_token:
        Logger.error("The Diving-Fish device code exchange returned no refresh token.")
        return False
    subject = token.get("sub")
    return await DivingProberBindInfo.set_bind_info(
        union_id=union_id,
        username="",
        refresh_token=str(refresh_token),
        subject=str(subject) if subject is not None else None,
    )


async def bind_account(msg) -> None:
    """以设备码流程引导用户完成一次水鱼账号绑定。

    :param msg: 消息会话。
    """
    if not DF_OAUTH_ENABLED:
        await msg.finish(I18NContext("maimai.message.oauth.not_configured"))
    try:
        device = await request_device_code(binding_label(msg.session_info))
    except DivingFishOAuthError:
        Logger.exception()
        await msg.finish(I18NContext("maimai.message.oauth.failed"))

    msg_chain = MessageChain.assign(
        [
            I18NContext("maimai.message.oauth.prompt", minutes=max(1, device.expires_in // 60)),
            Url(device.verification_uri_complete, trusted=True),
        ]
    )
    if not DF_CONFIDENTIAL_CLIENT:
        msg_chain.append(I18NContext("maimai.message.oauth.prompt.warn"))
    await msg.send_message(msg_chain, quote=False)

    deadline = time.monotonic() + device.expires_in
    interval = device.interval
    token = None
    try:
        while time.monotonic() < deadline:
            await msg.sleep(min(interval, max(0.0, deadline - time.monotonic())))
            try:
                token = await poll_device_token(device.device_code)
            except DivingFishSlowDown:
                interval += _SLOW_DOWN_STEP
                continue
            if token:
                break
        if not token:
            raise DivingFishDeviceCodeExpired("The user did not finish binding in time.")
    except DivingFishAuthorizationDenied:
        await msg.finish(I18NContext("maimai.message.oauth.denied"))
    except DivingFishDeviceCodeExpired:
        await msg.finish(I18NContext("maimai.message.oauth.expired"))
    except DivingFishOAuthError:
        Logger.exception()
        await msg.finish(I18NContext("maimai.message.oauth.failed"))

    union_id = msg.session_info.sender_union_id
    # 令牌此刻已经在手，而同一设备码无法换取第二次：先落盘，再做其它事情。
    if not await store_binding(union_id, token):
        await msg.finish(I18NContext("maimai.message.oauth.failed"))
    _cache_token(union_id, str(token["access_token"]), _expires_in(token))
    bind_info = await DivingProberBindInfo.get_by_sender_id(msg, create=False)
    nickname = await fill_bind_username(bind_info) if bind_info else ""
    subject = token.get("sub")
    await msg.finish(I18NContext("maimai.message.bind.success", username=nickname or str(subject or "")))


async def unbind_account(msg) -> None:
    """撤销授权并删除本地绑定记录。

    :param msg: 消息会话。
    """
    bind_info = await DivingProberBindInfo.get_by_sender_id(msg, create=False)
    if bind_info:
        # 机密客户端手上没有 refresh token，退而撤销仍在缓存里的 access token。
        token = bind_info.refresh_token
        token_type_hint = "refresh_token"
        if not token:
            token = _cached_access_token(bind_info.union_id)
            token_type_hint = "access_token"
        if token:
            try:
                await revoke_token(token, token_type_hint)
            except Exception:
                Logger.exception()
        drop_access_token(bind_info.union_id)
    await DivingProberBindInfo.remove_bind_info(union_id=msg.session_info.sender_union_id)
    await msg.finish(I18NContext("maimai.message.unbind.success"))
