import os
import sys

from core.elements import MessageSession
from core.loader.decorator import command
from database import BotDBUtil


@command('add_su', need_superuser=True, help_doc='add_su <user>')
async def add_su(message: MessageSession):
    user = message.parsed_msg['<user>']
    if user:
        if BotDBUtil.SenderInfo(f'{message.target.senderFrom}|{user}').edit('isSuperUser', True):
            await message.sendMessage('成功')


@command('del_su', need_superuser=True, help_doc='del_su <user>')
async def del_su(message: MessageSession):
    user = message.parsed_msg['<user>']
    if user:
        if BotDBUtil.SenderInfo(f'{message.target.senderFrom}|{user}').edit('isSuperUser', False):
            await message.sendMessage('成功')


"""
@command('set_modules', need_superuser=True, help_doc='set_modules <>')
async def set_modules(display_msg: dict):
    ...
"""


@command('restart', need_superuser=True)
async def restart_bot(msg: MessageSession):
    await msg.sendMessage('你确定吗？')
    confirm = await msg.waitConfirm()
    if confirm:
        await msg.sendMessage('已执行。')
        python = sys.executable
        os.execl(python, python, *sys.argv)

"""
async def update_bot(display_msg: dict):
    await sendMessage(display_msg, '你确定吗？')
    confirm = await wait_confirm(display_msg)
    if confirm:
        result = os.popen('git pull', 'r')
        await sendMessage(display_msg, result.read())


async def update_and_restart_bot(display_msg: dict):
    await sendMessage(display_msg, '你确定吗？')
    confirm = await wait_confirm(display_msg)
    if confirm:
        update = os.path.abspath('.cache_restart_author')
        write_version = open(update, 'w')
        write_version.write(json.dumps({'From': display_msg[Target].target_from, 'ID': display_msg[Target].id}))
        write_version.close()
        result = os.popen('git pull', 'r')
        await sendMessage(display_msg, result.read())
        python = sys.executable
        os.execl(python, python, *sys.argv)     
"""

@command('echo', need_superuser=True, help_doc='echo <display_msg>')
async def echo_msg(msg: MessageSession):
    await msg.sendMessage(msg.parsed_msg['<display_msg>'])
