# https://github.com/XeroAlpha/caidlist/blob/master/backend/API.md
import urllib.parse

from core.builtins import Bot
from core.component import module
from core.utils.http import get_url

api = 'https://ca.projectxero.top/idlist/search'

i = module('idlist', support_languages=['zh_cn'])


@i.command('<query> {{idlist.help}}')
async def _(msg: Bot.MessageSession, query: str):
    query_options = {'q': query, 'limit': '6'}
    query_url = api + '?' + urllib.parse.urlencode(query_options)
    resp = await get_url(query_url, 200, fmt='json')
    result = resp['data']['result']
    plain_texts = []
    if result:
        for x in result[0:5]:
            plain_texts.append(f'{x["enumName"]}：{x["key"]} -> {x["value"]}')
        if resp['data']['count'] > 5:
            plain_texts.append(msg.locale.t('message.collapse', amount='5') + msg.locale.t('idlist.message.collapse'))
            plain_texts.append('https://ca.projectxero.top/idlist/' + resp['data']['hash'])
        await msg.finish('\n'.join(plain_texts))
    else:
        await msg.finish(msg.locale.t('idlist.message.none'))
