import ujson as json

from core.logger import Logger
from core.utils.http import post_url
from core.utils.i18n import Locale


async def nbnhhsh(term: str, locale: Locale):
    '''查询nbnhhsh。
    :param term: 需要查询的term。
    :returns: 查询结果。'''
    try:
        url = 'https://lab.magiconch.com/api/nbnhhsh/guess'
        req = json.dumps({'text': term})
        data = await post_url(url, data=req, headers={'Content-Type': 'application/json', 'Accept': '*/*',
                                                      'Content-Length': str(len(req))}, fmt='json')
        Logger.debug(data)
        try:
            result = data[0]
        except IndexError:
            return f'[{locale.t("meme.message.nbnhhsh")}] {locale.t("meme.message.not_found")}'
        if 'trans' in result:
            trans = result['trans']
            count = trans.__len__()
            return f'[{locale.t("meme.message.nbnhhsh")}] {locale.t("meme.message.nbnhhsh.result", result=count)}{"、".join(trans)}'
        elif 'inputting' in result and result['inputting']:
            inputting = result['inputting']
            count = inputting.__len__()
            return f'[{locale.t("meme.message.nbnhhsh")}] {locale.t("meme.message.nbnhhsh.result.ai", result=count)}{"、".join(inputting)}'
        else:
            return f'[{locale.t("meme.message.nbnhhsh")}] {locale.t("meme.message.not_found")}'
    except Exception:
        return f'[{locale.t("meme.message.nbnhhsh")}] {locale.t("meme.message.error")}'
