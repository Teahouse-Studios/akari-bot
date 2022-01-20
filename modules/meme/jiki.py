import traceback

import ujson as json

from core.elements import Url
from core.utils.bot import post_url


async def jiki(term: str):
    '''查询小鸡百科。

    :param term: 需要查询的term。
    :returns: 查询结果。'''
    try:
        url = 'https://api.jikipedia.com/go/search_entities' + term
        text = await post_url(url, data={'page': 1, 'phrase': term, 'size': 1}, headers={'accept': '*/*',
                                                                                         'accept-encoding': 'gzip, deflate',
                                                                                         'accept-language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7,en-GB;q=0.6',
                                                                                         'content-type': 'application/json',
                                                                                         'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36 Edg/96.0.1054.62'})
        print(text)
        data = json.loads(text)
        count = data['total']
        result = data['data'][0]['definitions']
        title = result['term']['title']
        content = result['plaintext']
        link = 'https://jikipedia.com/definition/' + result['id']
        return f'[小鸡百科]（{count}个结果）：{title}\n{content}\n{str(Url(link))}'
    except Exception:
        traceback.print_exc()
        return '[小鸡百科] 查询出错。'
