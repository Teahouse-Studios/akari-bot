from core.builtins import Bot
from core.component import module
from core.builtins.message import MessageSession
from core.dirty_check import check
from core.utils.http import get_url

hitokoto = module('hitokoto', developers=['bugungu', 'DoroWolf'], desc='{hitokoto.help.desc}')

@hitokoto.handle('{{hitokoto.help}}')

async def _(msg: Bot.MessageSession):
    url = 'https://v1.hitokoto.cn/?encode=json'
    data = await get_url(url, 200, fmt = 'json')
    from_who = data["from_who"] or ""
    types = msg.locale.t('hitokoto.message.type') + msg.locale.t('hitokoto.message.type.' + data['type'])
    link = 'https://hitokoto.cn?id='
    await msg.sendMessage(f'''{data["hitokoto"]}\n——{from_who}「{data["from"]}」\n{types}\n{link}{data["id"]}''')