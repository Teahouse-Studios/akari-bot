import traceback

import ujson as json

from core.utils import post_url

async def nbnhhsh(term: str):
    '''查询nbnhhsh。
    :param term: 需要查询的term。
    :returns: 查询结果。'''
    try:
        url = 'https://lab.magiconch.com/api/nbnhhsh/guess'
        req = json.dumps({'text': term})
        text = await post_url(url, data=req, headers={'Content-Type': 'application/json', 'Accept': '*/*', 'Content-Length': str(len(req))})
        print(text)
        data = json.loads(text)
        result = data[0]
        if 'trans' in result:
            trans = result['trans']
            count = trans.__len__()
            return f'[nbnhhsh]（{count}个结果，已收录）：{"、".join(trans)}'
        elif 'inputting' in result and result['inputting'] != []:
            inputting = result['inputting']
            count = inputting.__len__()
            return f'[nbnhhsh]（{count}个结果，AI 猜测）：{"、".join(inputting)}'
        else:
            return '[nbnhhsh] 没有找到相关结果。'
    except Exception:
        traceback.print_exc()
        return '[nbnhhsh] 查询出错。'
