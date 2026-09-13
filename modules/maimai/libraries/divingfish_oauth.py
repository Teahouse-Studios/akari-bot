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
    """该用户未授权本应用，换票被拒。

    换票是「应用凭据 + 用户标识」查表，查不到人（授权已撤销，或用户不存在）即返回此错。
    归在 :class:`DivingFishTokenRevoked` 之下，使各处既有的「引导用户重新绑定」处理直接
    生效——两种情况对用户而言要做的事完全相同。
    """


class DivingFishRateLimited(DivingFishOAuthError):
    """请求过于频繁，授权服务器要求稍后再试。

    消息以状态码开头，便于沿用各调用点既有的 `str(e).startswith("429")` 分支。
    """


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


def diving_fish_bind_usable(bind_info: DivingProberBindInfo | None, confidential: bool | None = None) -> bool:
    """判断一条水鱼绑定记录当前是否可用于取分。

    公开客户端凭 refresh token 查分，令牌在记录即可用；机密客户端凭换票查分，只要有水鱼
    用户 ID 就能换到令牌。

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
    """按应用登记的形态补上客户端凭据。

    令牌端点严格比对认证方式：机密客户端少传 client_secret、公开客户端多传，得到的都是
    `401 invalid_client`，且两种情形的响应完全相同。故只能由配置里有无 client_secret 决定。

    :param payload: 表单字段。
    :return: 补全后的表单字段。
    """
    if DF_CONFIDENTIAL_CLIENT:
        payload["client_secret"] = DF_CLIENT_SECRET
    return payload


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

    公开客户端调用该端点时无需凭据，任何人都能用本应用的 client_id 生成一条绑定链接；机密
    客户端则会校验 client_secret。因此两种情况都要求调用方把用户码显示在用户自己触发的会话
    里，不可做成「把链接转发给需要绑定的人」的形式。

    :param label: 遮挡后的身份展示串，即 :func:`binding_label` 的结果。
    :return: 设备码与授权链接等数据。
    :raise DivingFishOAuthError: 发起失败，如应用信息未补全、scope 未获批准。
    """
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

    公开客户端无法换票，用户令牌（含 refresh token）只在这一次轮询的响应中出现，因此必须
    轮询到底；机密客户端本可放着设备码不管、等待下一次换票，但轮询是唯一能得知用户究竟点了
    同意还是拒绝的途径，且响应中的水鱼用户 ID 正是后续换票所需的标识，故同样轮询。

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

    只有公开客户端会走到这里：机密客户端的令牌响应里没有 refresh token，续期一律走换票。

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

    这是机密客户端唯一需要的取数方式。授权服务器会依次核对应用凭据、该用户是否授权过本应用、
    申请的 scope 是否落在用户的授权范围之内，任何一步不过都取不到令牌；`subject` 只是查表用
    的标识，本身不是凭据。此处不传 `scope`：省略时服务器取「用户授权范围」与「应用已批准范围」
    的交集，正好是用户当初在授权页里勾选的那些权限，比照着 :data:`DF_SCOPES` 再要一遍更宽松
    ——用户若只勾了一部分，后者会以「scope not granted」落进 `consent_required`，把「少勾了
    一项」误报成「授权已撤销」。

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
    """把 access token 记入进程内缓存。"""
    _access_token_cache[union_id] = (token, time.monotonic() + max(0.0, expires_in - _TOKEN_EXPIRE_MARGIN))


def _cached_access_token(union_id: str) -> str | None:
    """取出仍在有效期内的 access token，没有则返回 `None`。"""
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

    公开客户端以 refresh token 续期：刷新会轮换令牌，旧的再次出现时授权服务器会视其为凭据
    泄露、吊销整条令牌链，因此同一用户不得并发刷新，这里按 union_id 加锁；且新令牌必须先落盘
    再返回——进程若在落盘前退出，旧令牌已作废，用户就只能重新绑定一次。
    机密客户端改为换票，凭据在应用手上、令牌也无需落盘，但换得的令牌只有 5 分钟且同一用户每
    小时至多 60 次，同样要复用缓存与加锁。

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


async def revoke_token(token: str, token_type_hint: str = "refresh_token") -> None:
    """撤销一枚令牌，立即切断本应用对该用户的访问。

    用户也可以自行在水鱼账号的设置页撤销授权。解绑是最佳努力：即便撤销失败，本地记录也须
    照常删除。

    :param token: 要撤销的令牌。
    :param token_type_hint: `refresh_token` 或 `access_token`。它只是提示，撤销与否由服务器
        按令牌本身判断。
    :raise DivingFishOAuthError: 撤销请求失败。
    """
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


async def store_binding(union_id: str, token: dict) -> bool:
    """把一次成功的设备码绑定落盘。

    公开客户端没有别的凭据来源，refresh token 必须存下，此后凭它自行续期；机密客户端凭换票
    取数，只留水鱼用户 ID，并顺手清掉旧流程可能留下的 refresh token——那枚令牌此后不再被
    使用，留着只是多一份需要照看的长期凭据。

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

    用户码只在发起绑定的这场会话中展示：链接一旦被转发给他人，对方点下同意，令牌就落在转发
    者手上。轮询成功后落盘什么由客户端形态决定，见 :func:`store_binding`。

    :param msg: 消息会话。
    """
    if not DF_OAUTH_ENABLED:
        await msg.finish(I18NContext("maimai.message.oauth.not_configured"))
    try:
        device = await request_device_code(binding_label(msg.session_info))
    except DivingFishOAuthError:
        Logger.exception()
        await msg.finish(I18NContext("maimai.message.oauth.failed"))

    msg_chain = (
        MessageChain.assign(
            [
                I18NContext("maimai.message.oauth.prompt", minutes=max(1, device.expires_in // 60)),
                Url(device.verification_uri_complete, trusted=True),
            ]
        ),
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

    解绑由用户自己发起，故这里的撤销是收回他人手里那枚令牌的最后机会。

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
