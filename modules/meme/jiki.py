import traceback

import ujson as json

from core.utils.bot import post_url

async def jiki(term: str):
    '''查询小鸡百科。

    :param term: 需要查询的term。
    :returns: 查询结果。'''
    try:
        url = 'https://api.jikipedia.com/go/search_entities' + term
        text = await post_url(url, data={'page': 1, 'phrase': term, 'size': 1})
        print(text)
        data = json.loads(text)
        count = data['total']
        result = data['data'][0]['definitions']
        title = result['term']['title']
        content = result['plaintext']
        link = 'https://jikipedia.com/definition/' + result['id']
        return f'[小鸡百科]（{count}个结果）：{title}\n{content}\n{link}'
    except Exception:
        traceback.print_exc()
        return '[小鸡百科] 查询出错。'
