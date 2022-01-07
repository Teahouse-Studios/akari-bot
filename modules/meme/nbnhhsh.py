import traceback

import ujson as json

from core.utils import post_url

async def nbnhhsh(term: str):
    '''查询nbnhhsh。

    :param term: 需要查询的term。
    :returns: 查询结果。'''
    try:
        url = 'https://lab.magiconch.com/api/nbnhhsh/guess' + term
        text = await post_url(url, data={'text': term}, headers={'accept': '*/*',
            'accept-encoding': 'gzip, deflate',
            'accept-language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7,en-GB;q=0.6',
            'content-type': 'application/json',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36 Edg/96.0.1054.62'})
        print(text)
        data = json.loads(text)['data']
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
