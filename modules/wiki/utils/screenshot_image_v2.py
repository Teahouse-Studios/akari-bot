import traceback
from typing import Union

import ujson as json

from config import Config
from core.logger import Logger
from core.utils import download_to_cache

web_render = Config('web_render_local')


async def generate_screenshot(page_link, section=None, allow_special_page=False, doc_mode=False) -> Union[str, bool]:
    elements = ['.notaninfobox', '.portable-infobox', '.infobox', '.tpl-infobox', '.infoboxtable', '.infotemplatebox',
                '.skin-infobox', '.arcaeabox', '.moe-infobox']
    if not web_render:
        return False
    if section is None:
        if allow_special_page and doc_mode:
            page_link += '/doc'
            elements.insert(0, '.mw-parser-output')
        if allow_special_page and not doc_mode:
            elements.insert(0, '.diff')
        Logger.info('[Webrender] Generating element screenshot...')
        try:
            return await download_to_cache(web_render + 'element_screenshot', status_code=200,
                                           headers={'Content-Type': 'application/json'},
                                           method="POST",
                                           post_data=json.dumps({
                                               'url': page_link,
                                               'element': elements}),
                                           attempt=1, timeout=50,
                                           request_private_ip=True
                                           )
        except ValueError:
            traceback.print_exc()
            Logger.info('[Webrender] Generating Failed.')
            return False
    else:
        Logger.info('[Webrender] Generating section screenshot...')
        try:
            return await download_to_cache(web_render + 'section_screenshot', status_code=200,
                                           headers={'Content-Type': 'application/json'},
                                           method="POST",
                                           post_data=json.dumps({
                                               'url': page_link,
                                               'section': section}),
                                           attempt=1,
                                           request_private_ip=True
                                           )
        except ValueError:
            traceback.print_exc()
            Logger.info('[Webrender] Generating Failed.')
            return False
