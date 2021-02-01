from graia.application import Group, MessageChain, Member, Friend
from graia.application.message.elements.internal import Plain

import database
from core.template import sendMessage, check_permission


async def enable_modules(kwargs: dict):
    """
~enable [self] <modules/all>"""
    command = kwargs['trigger_msg'].split(' ')
    function_list = kwargs['function_list']
    if not len(command) > 1:
        await sendMessage(kwargs, '命令格式错误。' + enable_modules.__doc__)
        return
    command_second_word = command[1]
    if Group in kwargs:
        if command_second_word == 'self':
            if not len(command) > 2:
                await sendMessage(kwargs, '命令格式错误。' + enable_modules.__doc__)
                return
            command_third_word = command[2]
            if command_third_word in function_list:
                msg = database.update_modules_self('add', kwargs[Member].id, command_third_word)
                await sendMessage(kwargs, msg)
            else:
                await sendMessage(kwargs, '此模块不存在。')
        elif command_second_word == 'all':
            if check_permission(kwargs):
                msglist = []
                for function in function_list:
                    msg = database.update_modules('add', kwargs[Group].id, function)
                    msglist.append(msg)
                await sendMessage(kwargs, '\n'.join(msglist))
            else:
                await sendMessage(kwargs, '你没有使用该命令的权限。')
        elif command_second_word in function_list:
            if check_permission(kwargs):
                msg = database.update_modules('add', kwargs[Group].id, command_second_word)
                await sendMessage(kwargs, msg)
            else:
                await sendMessage(kwargs, '你没有使用该命令的权限。')
        else:
            msgchain = MessageChain.create([Plain('此模块不存在。')])
            await sendMessage(kwargs, msgchain)
    elif Friend in kwargs:
        if command_second_word == 'self':
            if not len(command) > 2:
                await sendMessage(kwargs, '命令格式错误。' + enable_modules.__doc__)
                return
            command_second_word = command[2]
        do = 'add'
        if command_second_word == 'all':
            msglist = []
            for function in function_list:
                msg = database.update_modules_self(do, kwargs[Friend].id, function)
                msglist.append(msg)
            await sendMessage(kwargs, '\n'.join(msglist))
        elif command_second_word in function_list:
            msg = database.update_modules_self(do, kwargs[Friend].id, command_second_word)
            await sendMessage(kwargs, msg)
        else:
            await sendMessage(kwargs, '此模块不存在。')


async def disable_modules(kwargs: dict):
    """
~disable [self] <modules/all>"""
    command = kwargs['trigger_msg'].split(' ')
    if not len(command) > 1:
        await sendMessage(kwargs, '命令格式错误。' + disable_modules.__doc__)
        return
    function_list = kwargs['function_list']
    command_second_word = command[1]
    if Group in kwargs:
        if command_second_word == 'self':
            if not len(command) > 2:
                await sendMessage(kwargs, '命令格式错误。' + disable_modules.__doc__)
                return
            command_third_word = command[2]
            if command_third_word in function_list:
                msg = database.update_modules_self('del', kwargs[Member].id, command_third_word)
                await sendMessage(kwargs, msg)
            else:
                await sendMessage(kwargs, '此模块不存在。')
        elif command_second_word == 'all':
            if check_permission(kwargs):
                msglist = []
                for function in function_list:
                    msg = database.update_modules('del', kwargs[Group].id, function)
                    msglist.append(msg)
                await sendMessage(kwargs, '\n'.join(msglist))
            else:
                await sendMessage(kwargs, '你没有使用该命令的权限。')
        elif command_second_word in function_list:
            if check_permission(kwargs):
                msg = database.update_modules('del', kwargs[Group].id, command_second_word)
                await sendMessage(kwargs, msg)
            else:
                await sendMessage(kwargs, '你没有使用该命令的权限。')
        else:
            await sendMessage(kwargs, '此模块不存在。')
    elif Friend in kwargs:
        if command_second_word == 'self':
            if not len(command) > 2:
                await sendMessage(kwargs, '命令格式错误。' + disable_modules.__doc__)
                return
            command_second_word = command[2]
        do = 'del'
        if command_second_word == 'all':
            msglist = []
            for function in function_list:
                msg = database.update_modules_self(do, kwargs[Friend].id, function)
                msglist.append(msg)
            await sendMessage(kwargs, '\n'.join(msglist))
        elif command_second_word in function_list:
            msg = database.update_modules_self(do, kwargs[Friend].id, command_second_word)
            await sendMessage(kwargs, msg)
        else:
            await sendMessage(kwargs, '此模块不存在。')


async def bot_help(kwargs: dict):
    help_list = kwargs['help_list']
    print(help_list)
    help_msg = []
    help_msg.append('基础命令：')
    for x in help_list:
        if 'essential' in help_list[x]:
            help_msg.append(help_list[x]['help'])
    help_msg.append('模块扩展命令：')
    for x in help_list:
        if Group in kwargs:
            if database.check_enable_modules(kwargs, x):
                if 'help' in help_list[x]:
                    help_msg.append(help_list[x]['help'])
            if 'depend' in help_list[x]:
                if database.check_enable_modules(kwargs, help_list[x]['depend']):
                    if help_list[x]['help'] not in help_msg:
                        help_msg.append(help_list[x]['help'])
        elif Friend in kwargs:
            if 'help' in help_list[x]:
                help_msg.append(help_list[x]['help'])
            if 'depend' in help_list[x]:
                if help_list[x]['help'] not in help_msg:
                    help_msg.append(help_list[x]['help'])
    await sendMessage(kwargs, '\n'.join(help_msg))


async def modules_help(kwargs: dict):
    help_list = kwargs['help_list']
    help_msg = []
    help_msg.append('当前可用的模块有：')
    for x in help_list:
        if 'module' in help_list[x]:
            help_msg.append(x + '：' + help_list[x]['module'])
    await sendMessage(kwargs, '\n'.join(help_msg))


async def add_su(kwargs: dict):
    command = kwargs['trigger_msg'].split(' ')
    if database.check_superuser(kwargs):
        await sendMessage(kwargs, database.add_superuser(command[1]))
    else:
        await sendMessage(kwargs, '权限不足。')


async def del_su(kwargs: dict):
    command = kwargs['trigger_msg'].split(' ')
    if database.check_superuser(kwargs):
        await sendMessage(kwargs, database.del_superuser(command[1]))
    else:
        await sendMessage(kwargs, '权限不足。')


async def add_base_su(kwargs: dict):
    await sendMessage(kwargs, database.add_superuser('2596322644'))

essential = {'enable': enable_modules, 'disable': disable_modules, 'help': bot_help, 'modules': modules_help}
admin = {'add_su': add_su, 'del_su': del_su, 'add_base_su': add_base_su}
help = {'enable': {'module': '开启一个模块', 'help': '~enable <模块名> - 开启一个模块', 'essential': True},
        'disable': {'module': '关闭一个模块', 'help': '~disable <模块名> - 关闭一个模块', 'essential': True},
        'module': {'help': '~modules - 查询所有可用模块。'}}
