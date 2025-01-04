from core.builtins import Bot
from core.component import module

zl = module('zhongli', alias={'zl': 'zhongli', 'zinfo': 'zhongli info',
                                  'stats': 'zhongli stats', 'bind': 'zhongli bind', 'check-in': 'zhongli check-in'
                                  }, desc='对接钟离（ 万 物 互 联 ）', developers=['haoye_qwq', 'xiaozhu_zhizui'],
                available_for=['QQ|Group', 'QQ', 'TEST|Console'])


def zlcm(cmd, sender, return_to):
    qq_sender_id = sender[3:]
    ret = f":execute as {qq_sender_id} return_to {return_to} run {cmd}"
    return ret


@zl.handle('info {获取服务器信息}')
async def zlinfo(send: Bot.MessageSession):
    cmd = 'info'
    sender = send.target.senderId
    return_to = send.target.targetId
    scmd = zlcm(cmd, sender, return_to)
    await Bot.FetchTarget.post_message('zhongli-probe', scmd)


@zl.handle('stats {获取战寄}')
async def zlstats(send: Bot.MessageSession):
    cmd = 'stats'
    sender = send.target.senderId
    return_to = send.target.targetId
    scmd = zlcm(cmd, sender, return_to)
    await Bot.FetchTarget.post_message('zhongli-probe', scmd)


@zl.handle('bind <MinecraftUserName> {绑定}')
async def zlbind(send: Bot.MessageSession):
    name = send.parsed_msg['<MinecraftUserName>']
    cmd = 'bind ' + name
    sender = send.target.senderId
    return_to = send.target.targetId
    scmd = zlcm(cmd, sender, return_to)
    await Bot.FetchTarget.post_message('zhongli-probe', scmd)


@zl.handle('check-in {签到}')
async def zlchk(send: Bot.MessageSession):
    cmd = '不能签，怎么想都不能签吧！'
    await send.sendMessage(cmd)


@zl.handle('send <msg> {以Admin发送命令}', required_superuser=True)
async def send_m(msg: Bot.MessageSession):
    sender = msg.target.senderId
    cmd = msg.parsed_msg['<msg>']
    return_to = msg.target.targetId
    await Bot.FetchTarget.post_message('zhongli-probe', f"-execute as {sender} return_to {return_to} run {cmd}")
