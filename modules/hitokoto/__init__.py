from core.builtins import Bot
from core.component import module
from core.utils.http import get_url

msg_types = ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l"]

hitokoto = module(
    'hitokoto',
    developers=['bugungu', 'DoroWolf'],
    desc='{hitokoto.help.desc}',
    alias='htkt',
    support_languages=['zh_cn'])


@hitokoto.handle()
@hitokoto.handle('[<msg_type>] {{hitokoto.help.type}}')
async def _(msg: Bot.MessageSession, msg_type: str = None):
    url = f'https://v1.hitokoto.cn/'
    if msg_type:
        if msg_type in msg_types:
            url += "?c=" + msg_type
        else:
            await msg.finish(msg.locale.t('hitokoto.message.error.type'))

    data = await get_url(url, 200, fmt='json')
    from_who = data["from_who"] or ""
    tp = msg.locale.t('hitokoto.message.type') + msg.locale.t('hitokoto.message.type.' + data['type'])
    link = f"https://hitokoto.cn?id={data['id']}"
    await msg.finish(f"{data['hitokoto']}\n——{from_who}「{data['from']}」\n{tp}\n{link}")
