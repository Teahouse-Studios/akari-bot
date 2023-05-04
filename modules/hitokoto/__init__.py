from core.builtins import Bot
from core.component import module
from core.builtins.message import MessageSession
from core.dirty_check import check
from core.utils.http import get_url

hitokoto = module('hitokoto', developers=['bugungu'], desc='{hitokoto.help.desc}')

@hitokoto.handle('{{hitokoto.help}}')

async def print_out(msg: Bot.MessageSession):
    url = 'https://v1.hitokoto.cn/?encode=json'
    responce = responce = await get_url(url, 200, fmt = 'json')
    if responce['from_who'] != None:
        send_msg = msg.locale.t("hitokoto.message") + ' #' + str(responce['id']) + '\n\n' + responce['hitokoto'] + '\n\n' + msg.locale.t("hitokoto.message.from") + msg.locale.t('hitokoto.type2name.' + responce['type']) + ' - ' + responce['from'] + ' - ' + responce['from_who']
    else:
        send_msg = msg.locale.t("hitokoto.message") + ' #' + str(responce['id']) + '\n\n' + responce['hitokoto'] + '\n\n' + msg.locale.t("hitokoto.message.from") + msg.locale.t('hitokoto.type2name.' + responce['type']) + ' - ' + responce['from'] + ' - ' + msg.locale.t("hitokoto.message.unknown")
    send = await msg.sendMessage(send_msg)