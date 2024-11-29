import traceback
from typing import Union

from core.config import Config
from core.constants.info import Info
from core.logger import Logger
from core.utils.http import get_url

web_render = Config('web_render', secret=True, get_url=True)
web_render_local = Config('web_render_local', get_url=True)


def webrender(method: str = '', url: str = '', use_local: bool = True) -> Union[str, None]:
    '''根据请求方法生成 WebRender URL。

    :param method: API 方法。
    :param url: 若 method 为 source，则指定请求的 URL。
    :param use_local: 是否使用本地 WebRender。
    :returns: 生成的 WebRender URL。
    '''
    if use_local and not Info.web_render_local_status:
        use_local = False
    if method == 'source':
        if Info.web_render_status:
            return f'{(web_render_local if use_local else web_render)}source?url={url}'
        else:
            return url
    else:
        if Info.web_render_status:
            return (web_render_local if use_local else web_render) + method
        else:
            return None


async def check_web_render():
    if not web_render_local:
        if not web_render:
            Logger.warning('[WebRender] WebRender is not configured.')
        else:
            Info.web_render_status = True
    else:
        Info.web_render_local_status = True
        Info.web_render_status = True
    ping_url = 'http://www.bing.com'
    if Info.web_render_status:
        try:
            Logger.info('[WebRender] Checking WebRender status...')
            await get_url(webrender('source', ping_url), 200, request_private_ip=True)
            Logger.info('[WebRender] WebRender is working as expected.')
        except Exception:
            Logger.error('[WebRender] WebRender is not working as expected.')
            Logger.error(traceback.format_exc())
            Info.web_render_status = False

__all__ = ['webrender']
