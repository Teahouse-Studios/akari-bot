# https://github.com/XeroAlpha/caidlist/blob/master/backend/API.md
import urllib.parse

from core.builtins import Bot
from core.component import module
from core.utils.http import get_url
from core.utils.i18n import get_target_locale

api = 'https://ca.projectxero.top/idlist/search'

i = module('idlist')


@i.handle('<query> {{idlist.desc}}')
async def _(msg: Bot.MessageSession):
    lang = get_target_locale(msg)
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
            plain_texts.append(lang.t('idlist.collapse'))
            plain_texts.append('https://ca.projectxero.top/idlist/' + resp['data']['hash'])
        await msg.finish('\n'.join(plain_texts))
    else:
        await msg.finish(lang.t('idlist.none'))
