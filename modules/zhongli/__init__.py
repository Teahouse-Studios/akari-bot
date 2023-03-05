from core.builtins import Bot
from core.component import on_command

zl = on_command('zhongli', alias='zl',desc='对接钟离（ 万 物 互 联 ）',developers=['haoye_qwq', 'xiaozhu_zhizui'])

@zl.handle('<command> {向钟离发送命令}')
async def zlc(send:Bot.MessageSession):
    cmd = send.parsed_msg['<command>']
    if '-bind' in cmd:await send.sendMessage('因对接方式问题，暂不支持该命令')
    elif '-load' in cmd:await send.sendMessage('因对接方式问题，暂不支持该命令')
    elif '-stats' in cmd:await send.sendMessage('因对接方式问题，暂不支持该命令')
    elif '-code' in cmd:await send.sendMessage('因对接方式问题，暂不支持该命令')
    elif '-check-in' in cmd:await send.sendMessage('因对接方式问题，暂不支持该命令')
    elif '-mute' in cmd:await send.sendMessage('因对接方式问题，暂不支持该命令')
    elif '-save' in cmd:await send.sendMessage('因对接方式问题，暂不支持该命令')
    elif '-load' in cmd:await send.sendMessage('因对接方式问题，暂不支持该命令')
    elif '-permission' in cmd:await send.sendMessage('因对接方式问题，暂不支持该命令')
    else:
        await Bot.FetchTarget.post_message('zhongli-probe', cmd)