from typing import Tuple, Optional
from urllib.parse import quote

from core.builtins import Info
from core.config import Config
from core.logger import Logger
from core.utils.http import get_url

web_render = Config("web_render", cfg_type=str, secret=True, get_url=True)


def webrender(
    method: str = "",
    url: str = "",
    _ignore_status=False,
) -> str:
    """根据请求方法生成 WebRender URL。

    :param method: API 方法。
    :param url: 若 method 为 source，则指定请求的 URL。
    :returns: 生成的 WebRender URL。
    """
    if _ignore_status and not web_render:
        return ""

    if method == "source":
        if Info.web_render_status or _ignore_status:
            return f"{web_render}source?url={quote(url)}"
        return url
    
    if Info.web_render_status or _ignore_status:
        return f"{web_render}{method}"
    return ""


async def check_web_render() -> bool:
    web_render_status = False
    if not web_render:
        Logger.warning("[WebRender] WebRender is not configured.")
    else:
        web_render_status = True
    ping_url = "http://www.bing.com"
    try:
        Logger.info("[WebRender] Checking WebRender status...")
        await get_url(
            webrender("source", ping_url, _ignore_status=True),
            200,
            request_private_ip=True,
            logging_err_resp=False
        )
        Logger.success("[WebRender] WebRender is working as expected.")
    except Exception:
        Logger.error("[WebRender] WebRender is not working as expected.")
        web_render_status = False

    return web_render_status


__all__ = ["webrender"]
