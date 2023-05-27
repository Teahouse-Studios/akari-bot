from core.builtins import Bot
from core.component import module
from core.builtins.message import MessageSession
from core.dirty_check import check
from core.utils.http import get_url

hitokoto_types = ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l"]

hitokoto = module('hitokoto', developers=['bugungu', 'DoroWolf'], desc='{hitokoto.help.desc}', alias=['htkt'], support_languages=['zh_cn'])

@hitokoto.handle('[<type>] {{hitokoto.help.type}}')

async def _(msg: Bot.MessageSession):
    try:
        set_type = msg.parsed_msg.get('<type>')
    except AttributeError:
        set_type = None
    url = 'https://v1.hitokoto.cn/?'
    if set_type is not None:
        if set_type not in hitokoto_types:
            await msg.finish(msg.locale.t('hitokoto.message.error.type'))
        else:
            url += "c=" + set_type
    data = await get_url(url, 200, fmt = 'json')
    from_who = data["from_who"] or ""
    _type = msg.locale.t('hitokoto.message.type') + msg.locale.t('hitokoto.message.type.' + data['type'])
    link = 'https://hitokoto.cn?id='
    await msg.finish(f'''{data["hitokoto"]}\n——{from_who}「{data["from"]}」\n{_type}\n{link}{data["id"]}''')