import traceback

import ujson as json

from core.logger import Logger
from core.utils.http import post_url


async def nbnhhsh(msg: int, term: str):
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
            return f'{msg.locale.t("meme.message.nbnhhsh")} {msg.locale.t("meme.message.not_found")}'
        if 'trans' in result:
            trans = result['trans']
            count = trans.__len__()
            return f'{msg.locale.t("meme.message.nbnhhsh")} {msg.locale.t("meme.message.nbnhhsh.result")}{"、".join(trans)}'
        elif 'inputting' in result and result['inputting'] != []:
            inputting = result['inputting']
            count = inputting.__len__()
            return f'{msg.locale.t("meme.message.nbnhhsh")} {msg.locale.t("meme.message.nbnhhsh.result.ai")}{"、".join(inputting)}'
        else:
            return f'{msg.locale.t("meme.message.nbnhhsh")} {msg.locale.t("meme.message.not_found")}'
    except Exception:
        traceback.print_exc()
        return f'{msg.locale.t("meme.message.nbnhhsh")} {msg.locale.t("meme.message.error")}'
