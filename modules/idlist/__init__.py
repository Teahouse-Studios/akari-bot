# https://github.com/XeroAlpha/caidlist/blob/master/backend/API.md
import urllib.parse

from core.builtins.message import MessageSession
from core.component import on_command
from core.utils import get_url

api = 'https://ca.projectxero.top/idlist/search'

i = on_command('idlist')


@i.handle('<query> {查询MCBEID表。}')
async def _(msg: MessageSession):
    query = msg.parsed_msg['<query>']
    query_options = {'q': query, 'limit': '6'}
    query_url = api + '?' + urllib.parse.urlencode(query_options)
    resp = await get_url(query_url, 200, fmt='json')
    result = resp['data']['result']
    plain_texts = []
    if result:
        for x in result[0:5]:
            plain_texts.append(f'{x["enumName"]}：{x["key"]} -> {x["value"]}')
        if resp['data']['count'] > 5:
            plain_texts.append('...仅显示前5条结果，查看更多：')
            plain_texts.append('https://ca.projectxero.top/idlist/' + resp['data']['hash'])
        await msg.finish('\n'.join(plain_texts))
    else:
        await msg.finish('没有找到结果。')
