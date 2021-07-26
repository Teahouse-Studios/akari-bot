import os
import sys
import json

from core.decorator import command
from core.elements import MessageSession
from database import BotDBUtil


@command('add_su', is_superuser_function=True, help_doc='add_su <user>')
async def add_su(message: MessageSession):
    user = message.parsed_msg['<user>']
    if user:
        if BotDBUtil.SenderInfo(f'{message.target.senderFrom}|{user}').edit('isSuperUser', True):
            await message.sendMessage('成功')


@command('del_su', is_superuser_function=True, help_doc='del_su <user>')
async def del_su(message: MessageSession):
    user = message.parsed_msg['<user>']
    if user:
        if BotDBUtil.SenderInfo(f'{message.target.senderFrom}|{user}').edit('isSuperUser', False):
            await message.sendMessage('成功')


"""
@command('set_modules', is_superuser_function=True, help_doc='set_modules <>')
async def set_modules(msg: dict):
    ...



async def restart_bot(kwargs: dict):
    await sendMessage(kwargs, '你确定吗？')
    confirm = await wait_confirm(kwargs)
    if confirm:
        update = os.path.abspath('.cache_restart_author')
        write_version = open(update, 'w')
        write_version.write(json.dumps({'From': kwargs[Target].target_from, 'ID': kwargs[Target].id}))
        write_version.close()
        await sendMessage(kwargs, '已执行。')
        python = sys.executable
        os.execl(python, python, *sys.argv)


async def update_bot(kwargs: dict):
    await sendMessage(kwargs, '你确定吗？')
    confirm = await wait_confirm(kwargs)
    if confirm:
        result = os.popen('git pull', 'r')
        await sendMessage(kwargs, result.read())


async def update_and_restart_bot(kwargs: dict):
    await sendMessage(kwargs, '你确定吗？')
    confirm = await wait_confirm(kwargs)
    if confirm:
        update = os.path.abspath('.cache_restart_author')
        write_version = open(update, 'w')
        write_version.write(json.dumps({'From': kwargs[Target].target_from, 'ID': kwargs[Target].id}))
        write_version.close()
        result = os.popen('git pull', 'r')
        await sendMessage(kwargs, result.read())
        python = sys.executable
        os.execl(python, python, *sys.argv)
"""


@command('echo', is_superuser_function=True, help_doc='echo <msg>')
async def echo_msg(msg: MessageSession):
    await msg.sendMessage(msg.parsed_msg['<msg>'])
