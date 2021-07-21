import os
import sys
import json

from core.elements.elements import Target
from core.bots.graia.template import sendMessage, wait_confirm
from database_old import BotDB as database


async def add_su(kwargs: dict):
    command = kwargs['trigger_msg'].split(' ')
    await sendMessage(kwargs, database.add_superuser(command[1]))


async def del_su(kwargs: dict):
    command = kwargs['trigger_msg'].split(' ')
    await sendMessage(kwargs, database.del_superuser(command[1]))


async def add_base_su(kwargs: dict):
    await sendMessage(kwargs, database.add_superuser('2596322644'))


async def set_modules(kwargs: dict):
    command = kwargs['trigger_msg'].split(' ')
    command_second_word = command[1]
    command_third_word = command[2]
    command_forth_word = command[3]
    msg = database.update_modules(command_second_word, command_third_word, command_forth_word)
    await sendMessage(kwargs, msg)


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


async def echo_msg(kwargs: dict):
    await sendMessage(kwargs, kwargs['trigger_msg'])
