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
from modules.maimai.config import MaimaiConfig
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

DF_SCOPE_MAIMAI = "prober.records.read"
DF_SCOPE_CHUNITHM = "chunithm.records.read"
DF_SCOPES = f"{DF_SCOPE_MAIMAI} {DF_SCOPE_CHUNITHM}"

_DEVICE_CODE_GRANT_TYPE = "urn:ietf:params:oauth:grant-type:device_code"
_TOKEN_EXPIRE_MARGIN = 30
_SLOW_DOWN_STEP = 5

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


@dataclass(frozen=True)
class DivingFishDeviceCode:
    """一次设备码绑定所需的数据。"""

    device_code: str
    user_code: str
    verification_uri: str
    verification_uri_complete: str
    expires_in: int
    interval: int


def _masked(value: str) -> str:
    """遮挡身份串的中间部分，保留首尾各两位。"""
    if len(value) < 5:
        return "*" * len(value)
    return f"{value[:2]}{'*' * (len(value) - 4)}{value[-2:]}"


def binding_label(session_info) -> str:
    """生成遮挡后的身份展示串，如 ``QQ 11****14``。

    设备码流程没有回调地址，同意页上的「绑定身份」是用户唯一可能察觉异常的地方：若有人把
    自己发起的绑定链接转发给他人，受害者只能靠这一行判断绑定的并非自己。故发起绑定时务必
    提交本串。

    :param session_info: 发起绑定的会话信息。
    :return: 遮挡后的展示串。
    """
    sender = str(session_info.get_common_sender_id())
    client = session_info.client_name or "Bot"
    return f"{client} {_masked(sender)}"


async def _post_form(url: str, payload: dict, *, attempt: int = 3, expect_json: bool = True) -> dict:
    """以 `application/x-www-form-urlencoded` 提交表单。

    OAuth 的错误以响应体中的 `error` 字段表达（如 `authorization_pending`），因此这里传
    `status_code=None`，使 4xx 响应也照常返回响应体而非抛出异常。

    :param url: 端点地址。
    :param payload: 表单字段。
    :param attempt: 请求尝试次数。令牌端点不做重试：设备码与 refresh token 都只能使用一次，
        重发可能扫掉第一次已签发的令牌。
    :param expect_json: 响应是否为 JSON。撤销端点成功时可能返回空响应体。
    :return: 响应体解析所得的字典；响应不是 JSON 对象时返回空字典。
    :raise DivingFishOAuthError: 请求失败。
    """
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
    """读取响应中的 `expires_in`，缺失或非法时按默认值处理。"""
    try:
        return float(resp.get("expires_in", default))
    except (TypeError, ValueError):
        return default


async def request_device_code(label: str) -> DivingFishDeviceCode:
    """发起一次设备码绑定，取得用户码与授权链接。

    公开客户端的该端点不校验凭据：任何人都能用本应用的 client_id 生成一条绑定链接。因此调用
    方必须把用户码显示在用户自己触发的会话里，不可做成「把链接转发给需要绑定的人」的形式。

    :param label: 遮挡后的身份展示串，即 :func:`binding_label` 的结果。
    :return: 设备码与授权链接等数据。
    :raise DivingFishOAuthError: 发起失败，如应用信息未补全、scope 未获批准。
    """
    resp = await _post_form(
        DF_DEVICE_AUTHORIZATION_URL,
        {
            "client_id": DF_CLIENT_ID,
            "scope": DF_SCOPES,
            "binding_label": label,
        },
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

    公开客户端无法换票，用户令牌只在这一次轮询的响应中出现，因此必须轮询到底。

    :param device_code: 设备码端点返回的设备码。
    :return: 令牌响应；用户尚未完成授权时返回 `None`。
    :raise DivingFishSlowDown: 轮询过快，调用方应延长间隔后继续。
    :raise DivingFishAuthorizationDenied: 用户拒绝授权。
    :raise DivingFishDeviceCodeExpired: 设备码已过期。
    :raise DivingFishOAuthError: 其它错误。
    """
    resp = await _post_form(
        DF_TOKEN_URL,
        {
            "grant_type": _DEVICE_CODE_GRANT_TYPE,
            "device_code": device_code,
            "client_id": DF_CLIENT_ID,
        },
        attempt=1,
    )
    error = resp.get("error")
    if not error:
        if not resp.get("access_token") or not resp.get("refresh_token"):
            raise DivingFishOAuthError(f"Device code exchange returned no token: {resp!r}")
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
        {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": DF_CLIENT_ID,
        },
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


def _cache_token(union_id: str, token: str, expires_in: float) -> None:
    """把 access token 记入进程内缓存。"""
    _access_token_cache[union_id] = (token, time.monotonic() + max(0.0, expires_in - _TOKEN_EXPIRE_MARGIN))


def drop_access_token(union_id: str) -> None:
    """丢弃缓存的 access token，供资源服务器判定令牌失效后重新刷新。

    :param union_id: 用户联合 ID。
    """
    _access_token_cache.pop(union_id, None)


async def get_access_token(bind_info: DivingProberBindInfo) -> str:
    """取得代表该绑定用户的 access token，未过期时复用进程内缓存。

    刷新会轮换 refresh token：旧的再次出现时，授权服务器会视其为凭据泄露并吊销整条令牌链。
    因此同一用户不得并发刷新，这里按 union_id 加锁；且新令牌必须先落盘再返回——进程若在
    落盘前退出，旧令牌已作废，用户就只能重新绑定一次。

    :param bind_info: 该用户的绑定记录。
    :return: access token。
    :raise DivingFishTokenRevoked: refresh token 已失效，用户需要重新绑定。
    :raise DivingFishOAuthError: 其它刷新错误。
    """
    union_id = bind_info.union_id
    cached = _access_token_cache.get(union_id)
    if cached and cached[1] > time.monotonic():
        return cached[0]

    lock = _refresh_locks.setdefault(union_id, asyncio.Lock())
    async with lock:
        # 等待期间可能已有一次刷新完成，复查缓存以免白白轮换一次令牌。
        cached = _access_token_cache.get(union_id)
        if cached and cached[1] > time.monotonic():
            return cached[0]
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

    令牌在请求前一刻取得（未过期则直接复用缓存）；若资源服务器判定令牌已失效（`401`），则
    丢弃缓存重新刷新并重试一次。

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


async def revoke_refresh_token(refresh_token: str) -> None:
    """撤销 refresh token，立即切断本应用对该用户的访问。

    用户也可以自行在水鱼账号的设置页撤销授权。解绑是最佳努力：即便撤销失败，本地记录也须
    照常删除。

    :param refresh_token: 要撤销的 refresh token。
    :raise DivingFishOAuthError: 撤销请求失败。
    """
    await _post_form(
        DF_REVOKE_URL,
        {
            "token": refresh_token,
            "token_type_hint": "refresh_token",
            "client_id": DF_CLIENT_ID,
        },
        expect_json=False,
    )


async def fill_bind_username(bind_info: DivingProberBindInfo) -> str:
    """补全绑定记录中的水鱼用户名，并返回昵称。

    查询对象已由令牌决定，多数端点并不需要用户名；但 B50 等公开端点仍只接受 `qq` 或
    `username`，非 QQ 平台因此需要留下用户名。用户名取自成绩端点响应，无需额外 scope。

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


async def bind_account(msg) -> None:
    """以设备码流程引导用户完成一次水鱼账号绑定。

    用户码只在发起绑定的这场会话中展示：该端点不校验凭据，链接一旦被转发给他人，对方点下
    同意，令牌就落在转发者手上。

    :param msg: 消息会话。
    """
    if not DF_OAUTH_ENABLED:
        await msg.finish(I18NContext("maimai.message.oauth.not_configured"))
    try:
        device = await request_device_code(binding_label(msg.session_info))
    except DivingFishOAuthError:
        Logger.exception()
        await msg.finish(I18NContext("maimai.message.oauth.failed"))

    await msg.send_message(
        MessageChain.assign(
            [
                I18NContext("maimai.message.oauth.prompt", minutes=max(1, device.expires_in // 60)),
                Url(device.verification_uri_complete, trusted=True),
                I18NContext("maimai.message.oauth.prompt.warn"),
            ]
        ),
        quote=False,
    )

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
    subject = token.get("sub")
    # 令牌此刻已经在手，而同一设备码无法换取第二次：先落盘，再做其它事情。
    if not await DivingProberBindInfo.set_bind_info(
        union_id=union_id,
        username="",
        refresh_token=str(token["refresh_token"]),
        subject=str(subject) if subject is not None else None,
    ):
        await msg.finish(I18NContext("maimai.message.oauth.failed"))
    _cache_token(union_id, str(token["access_token"]), _expires_in(token))
    bind_info = await DivingProberBindInfo.get_by_sender_id(msg, create=False)
    nickname = await fill_bind_username(bind_info) if bind_info else ""
    await msg.finish(I18NContext("maimai.message.bind.success", username=nickname or str(subject or "")))


async def unbind_account(msg) -> None:
    """撤销授权并删除本地绑定记录。

    :param msg: 消息会话。
    """
    bind_info = await DivingProberBindInfo.get_by_sender_id(msg, create=False)
    if bind_info and bind_info.refresh_token:
        try:
            await revoke_refresh_token(bind_info.refresh_token)
        except Exception:
            Logger.exception()
        drop_access_token(bind_info.union_id)
    await DivingProberBindInfo.remove_bind_info(union_id=msg.session_info.sender_union_id)
    await msg.finish(I18NContext("maimai.message.unbind.success"))
