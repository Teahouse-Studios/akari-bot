import traceback

from config import CFG
from core.logger import Logger
from core.utils.http import get_url
from core.utils.ip import IP

web_render = CFG.get_url('web_render')
web_render_local = CFG.get_url('web_render_local')

class WebRender:
    status = False
    local = False


def webrender(method: str = '', url: str = '', use_local: bool = True):
    '''根据请求方法生成 Webrender URL。

    :param method: API 方法。
    :param url: 若 method 为 source，则指定请求的 URL。
    :param use_local: 是否使用本地 Webrender。
    :returns: 生成的 Webrender URL。
    '''
    if use_local and not WebRender.local:
        use_local = False
    if method == 'source':
        if WebRender.status:
            return f'{(web_render_local if use_local else web_render)}source?url={url}'
        else:
            return url
    else:
        if WebRender.status:
            return (web_render_local if use_local else web_render) + method
        else:
            return None


async def check_web_render():
    if not web_render_local:
        if not web_render:
            Logger.warn('[Webrender] Webrender is not configured.')
        else:
            WebRender.status = True
    else:
        WebRender.local = True
        WebRender.status = True
    if IP.country != 'China':
        ping_url = 'http://www.google.com/'
    else:
        ping_url = 'http://www.baidu.com/'
    if WebRender.status:
        try:
            Logger.info('[Webrender] Checking Webrender status...')
            await get_url(webrender('source', ping_url), 200, request_private_ip=True)
            Logger.info('[Webrender] Webrender is working as expected.')
        except Exception:
            Logger.error('[Webrender] Webrender is not working as expected.')
            Logger.error(traceback.format_exc())
            WebRender.status = False