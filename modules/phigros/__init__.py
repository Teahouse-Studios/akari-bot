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

phi = module('phigros', developers=['OasisAkari'], desc='查询 Phigros 相关内容。SessionToken获取参考：'
                                                        'https://mivik.gitee.io/pgr-bot-help/index.html#%E5%AE%89%E5%8D%93',
             alias={'p': 'phigros', 'pgr': 'phigros', 'phi': 'phigros'})


@phi.command('bind <sessiontoken> {使用云存档SessionToken绑定一个账户。（请在私聊绑定账户）}')
async def _(msg: Bot.MessageSession):
    need_revoke = False
    send_msg = []
    if msg.target.targetFrom in ['QQ|Group', 'QQ|Guild', 'Discord|Channel', 'Telegram|group', 'Telegram|supergroup']:
        send_msg.append(await msg.sendMessage('警告：您正在群组中绑定账户，这有可能会使您的账户云存档数据被他人篡改。请尽量使用私聊绑定账户以避免这种情况。\n'
                                     '此次命令产生的消息将在15秒后撤回。'))
        need_revoke = True
    token: str = msg.parsed_msg['<sessiontoken>']
    bind = PgrBindInfoManager(msg).set_bind_info(sessiontoken=token)
    if bind:
        send_msg.append(await msg.sendMessage("成功绑定账户。"))
    if need_revoke:
        await msg.sleep(15)
        for i in send_msg:
            await i.delete()


@phi.command('unbind {取消绑定账户。}')
async def _(msg: Bot.MessageSession):
    unbind = PgrBindInfoManager(msg).remove_bind_info()
    if unbind:
        await msg.finish("成功取消绑定账户。")


@phi.command('b19 {查询B19信息。}')
async def _(msg: Bot.MessageSession):
    bind = PgrBindInfoManager(msg).get_bind_sessiontoken()
    if bind is None:
        await msg.finish("您还未绑定账户。")
    else:
        transport = TTransport.TBufferedTransport(TSocket.TSocket())
        protocol = TBinaryProtocol.TBinaryProtocol(transport)
        client = Phigros.Client(protocol)
        transport.open()
        saveurl = client.getSaveUrl(bind)
        result = client.best19(saveurl.saveUrl)
        await msg.sendMessage("查询结果：\n" + str(result))
        transport.close()
