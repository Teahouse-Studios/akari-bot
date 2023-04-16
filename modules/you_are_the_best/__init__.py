from core.component import on_command
from core.builtins.message import MessageSession
from core.dirty_check import check
from .yatb import yatb
from time import *

iamthebest = on_command(bind_prefix='iamthebest', alias='itb', developers=['bugungu'])

@iamthebest.handle('<user_name> {你最棒！}', required_admin = False, required_superuser = False, available_for = '*')

async def print_out(msg: MessageSession):
    user_name = msg.parsed_msg["<user_name>"]
    sendmsg = await yatb(user_name)
    if sendmsg != '':
        sendmsg += "\n[90秒后撤回消息][不要过多刷屏]"
        send = await msg.sendMessage(sendmsg)
        await msg.sleep(90)
        await send.delete()
        await msg.finish()
    return sendmsg