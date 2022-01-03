import ujson as json

from core.utils import get_url

async def urban(term: str):
    '''查询urban dictionary。

    :param term: 需要查询的term。
    :returns: 查询结果。'''
    try:
        url = 'http://api.urbandictionary.com/v0/define?term=' + term
        text = await get_url(url)
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
