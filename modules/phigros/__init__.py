from thrift.transport import TSocket
from thrift.transport import TTransport
from thrift.protocol import TBinaryProtocol

from .phigrosLibrary import Phigros
import traceback

from config import Config
from core.builtins import Bot
from core.builtins import Plain, Image
from core.component import module
from core.utils.http import get_url
from .dbutils import PgrBindInfoManager
from .update import update_difficulty_csv, update_assets
from .genb19 import drawb19

phi = module('phigros', developers=['OasisAkari'], desc='{phigros.help.desc}',
             alias={'p': 'phigros', 'pgr': 'phigros', 'phi': 'phigros'})


@phi.command('bind <sessiontoken> {{phigros.help.bind}}')
async def _(msg: Bot.MessageSession):
    need_revoke = False
    send_msg = []
    if msg.target.targetFrom in ['QQ|Group', 'QQ|Guild', 'Discord|Channel', 'Telegram|group', 'Telegram|supergroup']:
        send_msg.append(await msg.sendMessage(msg.locale.t("phigros.bind.message.warning")))
        need_revoke = True
    token: str = msg.parsed_msg['<sessiontoken>']
    bind = PgrBindInfoManager(msg).set_bind_info(sessiontoken=token)
    if bind:
        send_msg.append(await msg.sendMessage(msg.locale.t("phigros.bind.message.success")))
    if need_revoke:
        await msg.sleep(15)
        for i in send_msg:
            await i.delete()


@phi.command('unbind {{phigros.unbind.help}}')
async def _(msg: Bot.MessageSession):
    unbind = PgrBindInfoManager(msg).remove_bind_info()
    if unbind:
        await msg.finish(msg.locale.t("phigros.unbind.message.success"))


@phi.command('b19 {{phigros.b19.help}}')
async def _(msg: Bot.MessageSession):
    bind = PgrBindInfoManager(msg).get_bind_sessiontoken()
    if bind is None:
        await msg.finish(msg.locale.t("phigros.message.user_unbound"))
    else:
        transport = TTransport.TBufferedTransport(TSocket.TSocket())
        protocol = TBinaryProtocol.TBinaryProtocol(transport)
        client = Phigros.Client(protocol)
        transport.open()
        saveurl = client.getSaveUrl(bind)
        result = client.best19(saveurl.saveUrl)
        transport.close()
        await msg.sendMessage(Image(drawb19('', result)))


@phi.command('update', required_superuser=True)
async def _(msg: Bot.MessageSession):
    update_assets_ = await update_assets()
    update_difficulty_csv_ = await update_difficulty_csv()
    
    if update_assets_ and update_difficulty_csv_:
        await msg.finish(msg.locale.t("phigros.message.update.success"))
    else:
        if not update_assets_ and not update_difficulty_csv_:
            await msg.finish(msg.locale.t("phigros.message.update.failed"))
        elif not update_assets_:
            await msg.finish("not a")
        elif not update_difficulty_csv_:
            await msg.finish("not b")

 
@phi.command('update rating', required_superuser=True)
async def _(msg: Bot.MessageSession):
    update_ = await update_difficulty_csv()
    if update_:
        await msg.finish(msg.locale.t("phigros.message.update.success"))
