import traceback

import ujson as json

from config import CFG
from core.builtins import Url
from core.logger import Logger
from core.utils.http import get_url
from core.utils.i18n import Locale

web_render = CFG.get_url('web_render')
web_render_local = CFG.get_url('web_render_local')


async def urban(term: str, locale: Locale):
    '''查询urban dictionary。

    :param term: 需要查询的term。
    :returns: 查询结果。'''
    try:
        url = 'http://api.urbandictionary.com/v0/define?term=' + term
        if web_render:
            use_local = True if web_render_local else False
        else:
            return
        url = (web_render_local if use_local else web_render) + 'source?url=' + url
        text = await get_url(url, 200, headers={'accept': '*/*',
                                                'accept-encoding': 'gzip, deflate',
                                                'accept-language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7,en-GB;q=0.6',
                                                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36 Edg/96.0.1054.62'},
                             request_private_ip=True)
        Logger.debug(text)
        data = json.loads(text)['list']
        if not data:
            return f'[{locale.t("meme.message.urban")}] {locale.t("meme.message.not_found")}'
        else:
            count = data.__len__()
            word = data[0]['word']
            definition = limit_length(data[0]['definition'])
            example = limit_length(data[0]['example'])
            link = data[0]['permalink']
            return f'[{locale.t("meme.message.urban")}] {locale.t("meme.message.result", result=count)}\n{word}\n{definition}\nExample: {example}\n{str(Url(link))}'
    except Exception:
        traceback.print_exc()
        return f'[{locale.t("meme.message.urban")}] {locale.t("meme.message.error")}'


def limit_length(text, limit=50):
    new = text
    length = new.split(' ').__len__()
    if length > limit:
        new = ' '.join(new.split(' ')[0:limit]) + '…'
    return new
