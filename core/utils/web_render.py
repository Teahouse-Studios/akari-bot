import traceback
from typing import Tuple, Optional, Union

from core.config import Config
from core.constants.info import Info
from core.logger import Logger
from core.utils.http import get_url

web_render = Config("web_render", secret=True, get_url=True)
web_render_local = Config("web_render_local", get_url=True)


def webrender(
    method: str = "",
    url: Optional[str] = None,
    use_local: bool = True,
    _ignore_status=False,
) -> str:
    """根据请求方法生成 WebRender URL。

    :param method: API 方法。
    :param url: 若 method 为 source，则指定请求的 URL。
    :param use_local: 是否使用本地 WebRender。
    :returns: 生成的 WebRender URL。
    """
    if use_local and (not Info.web_render_local_status or _ignore_status):
        use_local = False
    if method == "source":
        url = "" if not url else url
        if Info.web_render_status or _ignore_status:
            return f"{(web_render_local if use_local else web_render)}source?url={url}"
    else:
        url = ""
        if Info.web_render_status or _ignore_status:
            return (web_render_local if use_local else web_render) + method
    return url


async def check_web_render() -> Tuple[bool, bool]:
    web_render_status = False
    web_render_local_status = False
    if not web_render_local:
        if not web_render:
            Logger.warning("[WebRender] WebRender is not configured.")
        else:
            web_render_status = True
    else:
        web_render_status = True
        web_render_local_status = True
    ping_url = "http://www.bing.com"
    if web_render_status:
        try:
            Logger.info("[WebRender] Checking WebRender status...")
            await get_url(
                webrender("source", ping_url, _ignore_status=True),
                200,
                request_private_ip=True,
            )
            Logger.info("[WebRender] WebRender is working as expected.")
        except Exception:
            Logger.error("[WebRender] WebRender is not working as expected.")
            Logger.error(traceback.format_exc())
            web_render_status = False
    return web_render_status, web_render_local_status


__all__ = ["webrender", "check_web_render"]
