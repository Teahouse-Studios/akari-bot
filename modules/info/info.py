from core.builtins import Bot, Image
from core.component import on_command
from core.extra import pir
import time

inf = on_command('info')


@inf.handle()
async def inf_helps(msg: Bot.MessageSession):
    inf = msg.options.get('command_alias')
    if inf is None:
        inf = {}
    else:
        if len(inf) == 0:
            await msg.sendMessage('自定义命令别名列表为空。')
        else:
            send = await msg.sendMessage(Image(pir(
                f'[90秒后撤回消息]自定义命令别名列表：\n' + '\n'.join([f'{k} -> {inf[k]}' for k in inf]))))
            time.sleep(90)
            send.delete()
