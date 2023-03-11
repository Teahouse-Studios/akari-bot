from core.builtins import Bot
from core.component import on_command
import re

zl = on_command('zhongli', alias={'zl' : 'zhongli', 'zinfo' : 'zhongli info', 
                                  'stats' : 'zhongli stats', 'bind' : 'zhongli bind', 'check-in' : 'zhongli check-in'
                                  },desc='对接钟离（ 万 物 互 联 ）',developers=['haoye_qwq', 'xiaozhu_zhizui'],available_for=['QQ|Group','QQ','TEST|Console'])

def zlcm(cmd, sender):
    qq_sender_id = re.match(r'^\d*',sender)
    return(f"-execute as {qq_sender_id} permission normal_user run {cmd}")

@zl.handle('info {获取服务器信息}')
async def zlinfo(send:Bot.MessageSession):
    cmd = '-info'
    sender = send.target.senderId
    scmd = zlcm(cmd, sender)
    await Bot.FetchTarget.post_message('zhongli-probe', scmd)

@zl.handle('stats {获取战寄}')
async def zlstats(send:Bot.MessageSession):
    cmd = '-stats'
    sender = send.target.senderId
    scmd = zlcm(cmd, sender)
    await Bot.FetchTarget.post_message('zhongli-probe', scmd)

@zl.handle('bind <MinecraftUserName> {绑定}')
async def zlbind(send:Bot.MessageSession):
    name = send.parsed_msg['<MinecraftUserName>']
    cmd = '-bind ' + name
    sender = send.target.senderId
    scmd = zlcm(cmd, sender)
    await Bot.FetchTarget.post_message('zhongli-probe', scmd)

@zl.handle('check-in {签到}')
async def zlchk(send:Bot.MessageSession):
    cmd = '不能签，怎么想都不能签吧！'
    await send.sendMessage(cmd)

@zl.handle('send <msg> {直接发送消息}', required_admin=True)
async def send(msg:Bot.MessageSession):
    cmd = msg.parsed_msg['<msg>']
    await Bot.FetchTarget.post_message('zhongli-probe', cmd)