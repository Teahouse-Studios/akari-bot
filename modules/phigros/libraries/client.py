from contextlib import asynccontextmanager

import httpx

from core.utils.http import proxy
from .PhiCloudActionAsync.ActionLib import DEFAULT_TIMEOUT, checkSessionToken
from .PhiCloudActionAsync.CloudAction import PhigrosCloud

# 令牌失效时 LeanCloud 以此二者应答。
_TOKEN_INVALID_STATUS = (401, 403)


def check_session_token(session_token: str) -> bool:
    """校验 sessionToken 格式，不合法时返回 False 而非抛出。

    :param session_token: 待校验的会话令牌。
    """
    return checkSessionToken(session_token, _raise=False)


def build_client() -> httpx.AsyncClient:
    """构造带项目代理配置的 HTTP 客户端。

    存档下载走 CDN 直链，必须跟随重定向，否则 PigeonRequest 中的 raise_for_status()
    会把 302 当作错误抛出。
    """
    return httpx.AsyncClient(follow_redirects=True, timeout=DEFAULT_TIMEOUT, proxy=proxy)


@asynccontextmanager
async def phigros_cloud(session_token: str, is_international: bool = False):
    """产出一个 PhigrosCloud，并在退出时关闭其底层客户端。

    :param session_token: 玩家的会话令牌。
    :param is_international: 是否为国际服账号。
    """
    client = build_client()
    try:
        yield PhigrosCloud(session_token, is_international, client)
    finally:
        await client.aclose()


def is_token_invalid(exc: BaseException) -> bool:
    """判断异常是否由令牌失效引起。

    :param exc: 待判断的异常。
    """
    return isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in _TOKEN_INVALID_STATUS
