import ujson as json

from core.utils import get_url

async def urban(term: str):
    '''查询urban dictionary。

    :param term: 需要查询的term。
    :returns: 查询结果。'''
    try:
        url = 'http://api.urbandictionary.com/v0/define?term=' + term
        text = await get_url(url, headers={'accept': '*/*',
            'accept-encoding': 'gzip, deflate',
            'accept-language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7,en-GB;q=0.6',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36 Edg/96.0.1054.62'})
        data = json.loads(text)['list']
        if data == []:
            return '[Urban Dictionary] 没有找到相关结果。'
        else:
            count = data.__len__()
            word = data[0]['word']
            defination = data[0]['definition']
            example = data[0]['example']
            link = data[0]['permalink']
            return f'[Urban Dictionary]（{count}个结果）：\n{word}\n{defination}\nExample: {example}\n{link}'
    except:
        return '[Urban Dictionary] 查询出错。'
