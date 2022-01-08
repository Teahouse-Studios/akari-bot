import traceback

import ujson as json

from core.elements import MessageSession
from core.component import on_command
from core.utils import post_url

n = on_command(
    bind_prefix='nbnhhsh',
    desc='能不能好好说话？拼音首字母缩写释义工具',
    developers=['Dianliang233'],)


@n.handle('<term>')
async def _(msg: MessageSession):
    await msg.sendMessage(await nbnhhsh(msg.parsed_msg['<term>']))

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
