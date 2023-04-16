from core.builtins import Bot
from core.component import module
from core.builtins.message import MessageSession
from core.dirty_check import check
from core.utils.http import get_url

hitokoto = module(bind_prefix='hitokoto', developers=['bugungu'])

@hitokoto.handle('{Get Hitokoto / 获取一言}', required_admin = False, required_superuser = False, available_for = '*')

async def print_out(msg: Bot.MessageSession):
    url = 'https://v1.hitokoto.cn/?encode=json'
    responce = responce = await get_url(url, 200, fmt = 'json')
    if responce['from_who'] != None:
        send_msg = msg.locale.t("hitokoto.name") + ' #' + str(responce['id']) + '\n\n' + responce['hitokoto'] + '\n\n' + msg.locale.t("hitokoto.come_from") + msg.locale.t('hitokoto.type2name.' + responce['type']) + ' - ' + responce['from'] + ' - ' + responce['from_who']
    else:
        send_msg = msg.locale.t("hitokoto.name") + ' #' + str(responce['id']) + '\n\n' + responce['hitokoto'] + '\n\n' + msg.locale.t("hitokoto.come_from") + msg.locale.t('hitokoto.type2name.' + responce['type']) + ' - ' + responce['from'] + ' - ' + msg.locale.t("hitokoto.unknown")
    send = await msg.sendMessage(send_msg + msg.locale.t("hitokoto.message.delete"))
    await msg.sleep(90)
    await send.delete()
    await msg.finish()
