"""落雪咖啡屋（LXNS）OAuth 授权。

落雪只提供授权码流程，没有设备码流程：应用无法替用户完成授权，用户必须在自己的浏览器里
打开授权链接并同意，页面随后直接显示授权码（应用登记为「无回调地址」时），用户再把这串
授权码发回会话。授权码只能使用一次，且兑换时必须带上发起授权时用的 PKCE 校验串。
"""

import asyncio
import base64
import hashlib
import secrets
import time
from typing import Any
from urllib.parse import urlencode

import orjson

from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import I18NContext, Url
from core.constants.exceptions import WaitCancelException
from core.logger import Logger
from core.utils.http import get_url, post_url
from modules.maimai.config import MaimaiConfig, MaimaiSecretConfig
from ..database.models import LxnsProberBindInfo

LXNS_AUTH_SERVER = "https://maimai.lxns.net"
LXNS_AUTHORIZE_URL = f"{LXNS_AUTH_SERVER}/oauth/authorize"
LXNS_TOKEN_URL = f"{LXNS_AUTH_SERVER}/api/v0/oauth/token"
LXNS_API_BASE = f"{LXNS_AUTH_SERVER}/api/v0"
LXNS_MAIMAI_PLAYER_URL = f"{LXNS_API_BASE}/user/maimai/player"
LXNS_CHUNITHM_PLAYER_URL = f"{LXNS_API_BASE}/user/chunithm/player"

# `read_player` 同时覆盖舞萌与中二的玩家信息、谱面成绩与历史成绩。
LXNS_SCOPE = "read_player"

LXNS_CLIENT_ID = MaimaiConfig.lxns_client_id
LXNS_CLIENT_SECRET = MaimaiSecretConfig.lxns_client_secret
LXNS_REDIRECT_URI = MaimaiSecretConfig.lxns_redirect_uri
LXNS_OAUTH_ENABLED = bool(LXNS_CLIENT_ID)

# 授权码要经由用户手动搬运一趟，等待时间给得比常规交互宽裕些。
AUTHORIZE_TIMEOUT = 300
_TOKEN_EXPIRE_MARGIN = 30

_access_token_cache: dict[str, tuple[str, float]] = {}
_refresh_locks: dict[str, asyncio.Lock] = {}


class LxnsOAuthError(Exception):
    """落雪 OAuth 流程失败。"""


class LxnsCodeInvalid(LxnsOAuthError):
    """授权码无效、已过期，或与客户端、回调地址不匹配。"""


class LxnsTokenRevoked(LxnsOAuthError):
    """refresh token 已失效：用户撤销了授权，或令牌链因并发刷新被吊销。"""


def generate_code_verifier() -> str:
    """生成 PKCE 校验串。

    :return: 随机校验串。
    """
    return secrets.token_urlsafe(64)


def generate_code_challenge(verifier: str) -> str:
    """按 S256 由校验串算出挑战值。

    :param verifier: 校验串。
    :return: base64url 编码（无填充）的挑战值。
    """
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def build_authorize_url(code_challenge: str, state: str) -> str:
    """拼出授权链接。

    应用登记为「无回调地址」时不带 `redirect_uri`，授权完成后页面直接显示授权码；已登记
    回调地址时必须带上，且须与登记值完全一致。

    :param code_challenge: PKCE 挑战值。
    :param state: 用于关联请求状态并防跨站请求伪造的随机串。
    :return: 授权链接。
    """
    query = {
        "response_type": "code",
        "client_id": LXNS_CLIENT_ID,
        "scope": LXNS_SCOPE,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "state": state,
    }
    if LXNS_REDIRECT_URI:
        query["redirect_uri"] = LXNS_REDIRECT_URI
    return f"{LXNS_AUTHORIZE_URL}?{urlencode(query)}"


def unwrap(resp: Any) -> Any:
    """取出落雪接口响应中被 `data` 包裹的结果。

    :param resp: 响应体。
    :return: `data` 字段的内容；响应未被包裹时原样返回。
    """
    if isinstance(resp, dict) and "data" in resp:
        return resp["data"]
    return resp


def _expires_in(resp: dict, default: float = 900.0) -> float:
    """读取响应中的 `expires_in`，缺失或非法时按默认值处理。"""
    try:
        return float(resp.get("expires_in", default))
    except (TypeError, ValueError):
        return default


async def _token_request(payload: dict) -> dict:
    """向令牌端点提交一次请求。

    令牌端点只用一次性的授权码或 refresh token，重发可能扫掉第一份已签发的令牌，故不重试。
    错误以响应体中的 `error` 字段表达，因此传 `status_code=None` 以读取 4xx 的响应体。

    :param payload: 请求体。
    :return: 响应体解析所得的字典。
    :raise LxnsOAuthError: 请求失败或响应格式异常。
    """
    try:
        resp = await post_url(
            LXNS_TOKEN_URL,
            data=orjson.dumps(payload),
            status_code=None,
            headers={"Content-Type": "application/json", "accept": "application/json"},
            fmt="json",
            attempt=1,
        )
    except Exception as e:
        raise LxnsOAuthError(str(e)) from e
    if not isinstance(resp, dict):
        raise LxnsOAuthError(f"Unexpected response: {resp!r}")
    return resp


def _check_client_config() -> None:
    """校验应用信息，免得把必然失败的请求发出去。"""
    if not LXNS_OAUTH_ENABLED:
        raise LxnsOAuthError("The LXNS OAuth client_id is not configured.")


async def exchange_code(code: str, code_verifier: str) -> dict:
    """以授权码换取访问令牌。

    :param code: 用户在授权页上取得的授权码。
    :param code_verifier: 发起授权时生成的 PKCE 校验串。
    :return: 令牌响应，含 `access_token`、`refresh_token` 与 `sub`。
    :raise LxnsCodeInvalid: 授权码无效、已过期，或与客户端、回调地址不匹配。
    :raise LxnsOAuthError: 其它错误。
    """
    _check_client_config()
    payload = {
        "client_id": LXNS_CLIENT_ID,
        "grant_type": "authorization_code",
        "code": code,
        "code_verifier": code_verifier,
    }
    if LXNS_CLIENT_SECRET:
        payload["client_secret"] = LXNS_CLIENT_SECRET
    if LXNS_REDIRECT_URI:
        payload["redirect_uri"] = LXNS_REDIRECT_URI
    resp = await _token_request(payload)
    error = resp.get("error")
    if error:
        if error == "invalid_grant":
            raise LxnsCodeInvalid(f"Authorization code is no longer valid: {resp.get('error_description', '')}")
        raise LxnsOAuthError(f"Authorization code exchange failed: {error}")
    if not resp.get("access_token") or not resp.get("refresh_token"):
        raise LxnsOAuthError(f"Authorization code exchange returned no token: {resp!r}")
    return resp


async def refresh_access_token(refresh_token: str) -> dict:
    """以 refresh token 换取新的访问令牌。

    刷新令牌有效期 30 天，每次刷新后响应都会给出新的 refresh token，旧的立即失效。

    :param refresh_token: 当前持有的 refresh token。
    :return: 令牌响应，含轮换后的 `refresh_token`。
    :raise LxnsTokenRevoked: 该 refresh token 已失效，用户需要重新绑定。
    :raise LxnsOAuthError: 其它刷新错误。
    """
    _check_client_config()
    payload = {
        "client_id": LXNS_CLIENT_ID,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    if LXNS_CLIENT_SECRET:
        payload["client_secret"] = LXNS_CLIENT_SECRET
    resp = await _token_request(payload)
    error = resp.get("error")
    if error:
        if error == "invalid_grant":
            raise LxnsTokenRevoked(f"Refresh token is no longer valid: {resp.get('error_description', '')}")
        raise LxnsOAuthError(f"Token refresh failed: {error}")
    if not resp.get("access_token"):
        raise LxnsOAuthError(f"Token refresh returned no access token: {resp!r}")
    return resp


def _cache_token(union_id: str, token: str, expires_in: float) -> None:
    """把 access token 记入进程内缓存。"""
    _access_token_cache[union_id] = (token, time.monotonic() + max(0.0, expires_in - _TOKEN_EXPIRE_MARGIN))


def drop_access_token(union_id: str) -> None:
    """丢弃缓存的 access token，供资源服务器判定令牌失效后重新刷新。

    :param union_id: 用户联合 ID。
    """
    _access_token_cache.pop(union_id, None)


async def get_access_token(bind_info: LxnsProberBindInfo) -> str:
    """取得代表该绑定用户的 access token，未过期时复用进程内缓存。

    刷新会轮换 refresh token：旧的再次出现时，授权服务器会视其为凭据泄露并吊销整条令牌链。
    因此同一用户不得并发刷新，这里按 union_id 加锁；且新令牌必须先落盘再返回——进程若在
    落盘前退出，旧令牌已作废，用户就只能重新绑定一次。

    :param bind_info: 该用户的绑定记录。
    :return: access token。
    :raise LxnsTokenRevoked: refresh token 已失效，用户需要重新绑定。
    :raise LxnsOAuthError: 其它刷新错误。
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
            raise LxnsTokenRevoked("No refresh token stored for this user.")
        resp = await refresh_access_token(refresh_token)
        rotated = str(resp.get("refresh_token") or refresh_token)
        subject = resp.get("sub")
        await LxnsProberBindInfo.update_refresh_token(
            union_id, rotated, subject=str(subject) if subject is not None else None
        )
        bind_info.refresh_token = rotated
        token = str(resp["access_token"])
        _cache_token(union_id, token, _expires_in(resp))
        return token


async def request_player_data(
    bind_info: LxnsProberBindInfo,
    url: str,
    *,
    method: str = "GET",
    data: Any = None,
    params: dict[str, Any] | None = None,
) -> Any:
    """携带代表该用户的 Bearer 令牌请求落雪端点。

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


async def fetch_player_name(bind_info: LxnsProberBindInfo, url: str = LXNS_MAIMAI_PLAYER_URL) -> str:
    """取得该账号在落雪上的玩家名，用于向用户确认绑定到了哪个账号。

    :param bind_info: 该用户的绑定记录。
    :param url: 舞萌或中二的玩家信息端点。
    :return: 玩家名；获取失败时返回空字符串。
    """
    try:
        profile = unwrap(await request_player_data(bind_info, url))
    except Exception:
        Logger.exception()
        return ""
    if not isinstance(profile, dict):
        return ""
    return str(profile.get("name", ""))


async def bind_account(msg) -> None:
    """以授权码流程引导用户完成一次落雪账号绑定。

    授权码只在用户自己的浏览器里生成：链接一旦被转发给他人，对方点下同意，令牌就落在
    转发者手上。故提示与授权码都必须留在发起绑定的这场会话里。

    :param msg: 消息会话。
    """
    if not LXNS_OAUTH_ENABLED:
        await msg.finish(I18NContext("maimai.message.oauth.lx.not_configured"))
    code_verifier = generate_code_verifier()
    authorize_url = build_authorize_url(generate_code_challenge(code_verifier), secrets.token_urlsafe(16))
    try:
        reply = await msg.wait_next_message(
            MessageChain.assign(
                [
                    I18NContext("maimai.message.oauth.lx.prompt", minutes=max(1, AUTHORIZE_TIMEOUT // 60)),
                    Url(authorize_url, trusted=True),
                ]
            ),
            quote=False,
            timeout=AUTHORIZE_TIMEOUT,
        )
    except WaitCancelException:
        await msg.finish(I18NContext("maimai.message.oauth.lx.timeout"))

    code = reply.as_display(text_only=True).strip()
    try:
        token = await exchange_code(code, code_verifier)
    except LxnsCodeInvalid:
        await reply.finish(I18NContext("maimai.message.oauth.lx.code_invalid"))
    except LxnsOAuthError:
        Logger.exception()
        await reply.finish(I18NContext("maimai.message.oauth.failed"))

    union_id = reply.session_info.sender_union_id
    subject = token.get("sub")
    # 令牌此刻已经在手，而同一授权码无法换取第二次：先落盘，再做其它事情。
    if not await LxnsProberBindInfo.set_bind_info(
        union_id=union_id,
        refresh_token=str(token["refresh_token"]),
        subject=str(subject) if subject is not None else None,
    ):
        await reply.finish(I18NContext("maimai.message.oauth.failed"))
    _cache_token(union_id, str(token["access_token"]), _expires_in(token))
    bind_info = await LxnsProberBindInfo.get_by_sender_id(reply, create=False)
    nickname = await fetch_player_name(bind_info) if bind_info else ""
    await reply.finish(I18NContext("maimai.message.bind.success", username=nickname or str(subject or "")))


async def unbind_account(msg) -> None:
    """删除本地绑定记录。

    落雪未提供令牌撤销端点，授权只能由用户在查分器的账号设置里自行撤销；这里至少让机器人
    不再持有该账号的凭据。

    :param msg: 消息会话。
    """
    bind_info = await LxnsProberBindInfo.get_by_sender_id(msg, create=False)
    if bind_info:
        drop_access_token(bind_info.union_id)
    await LxnsProberBindInfo.remove_bind_info(union_id=msg.session_info.sender_union_id)
    await msg.finish(I18NContext("maimai.message.unbind.success"))
