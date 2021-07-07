import asyncio

from graia.application import Group, MessageChain, Member, Friend
from graia.application.message.elements.internal import Plain

from core.template import check_permission, revokeMessage
from .admin import *
from core.decorator import command


@command(bind_prefix='module')
async def config_modules(kwargs: dict):
    """
~module <enable/disable> <module/all>"""
    command = kwargs['trigger_msg'].split(' ')
    bot_modules = kwargs['bot_modules']
    function_list = bot_modules['modules_function']
    friend_function_list = bot_modules['friend_modules_function']
    alias_list = bot_modules['alias']
    msg = '命令格式错误。' + config_modules.__doc__
    if not len(command) > 2:
        await sendMessage(kwargs, msg)
        return
    do = command[1]
    command_third_word = command[2]
    if command_third_word in alias_list:
        command_third_word = alias_list[command_third_word]
    if Group in kwargs:
        if not check_permission(kwargs):
            await sendMessage(kwargs, '你没有使用该命令的权限。')
            return
        if command_third_word == 'all':
            msglist = []
            for function in function_list:
                msg = database.update_modules(do, kwargs[Group].id, function)
                msglist.append(msg)
            msg = '\n'.join(msglist)
        elif command_third_word in function_list:
            msg = database.update_modules(do, kwargs[Group].id, command_third_word)
        else:
            msg = '此模块不存在。'
    elif Friend in kwargs:
        if command_third_word in friend_function_list:
            msg = database.update_modules(do, kwargs[Friend].id, command_third_word, table='friend_permission')
        else:
            msg = '此模块不存在。'
    await sendMessage(kwargs, msg)



async def bot_help(kwargs: dict):
    help_list = kwargs['bot_modules']['help']
    alias = kwargs['bot_modules']['alias']
    command = kwargs['trigger_msg'].split(' ')
    if len(command) > 1:
        msg = []
        help_name = command[1]
        if help_name in alias:
            help_name = alias[help_name].split(' ')[0]
        if help_name in help_list:
            msg.append(help_list[help_name]['help'])
            for x in help_list:
                if 'depend' in help_list[x]:
                    if help_list[x]['depend'] == help_name:
                        msg.append(help_list[x]['help'])
            await sendMessage(kwargs, '\n'.join(msg))
    else:
        print(help_list)
        help_msg = []
        help_msg.append('基础命令：')
        essential = []
        for x in help_list:
            if 'essential' in help_list[x]:
                essential.append(x)
        help_msg.append(' | '.join(essential))
        help_msg.append('模块扩展命令：')
        module = []
        for x in help_list:
            if Group in kwargs:
                if database.check_enable_modules(kwargs, x):
                    if 'help' in help_list[x]:
                        module.append(x)
            elif Friend in kwargs:
                if 'help' in help_list[x]:
                    module.append(x)
        help_msg.append(' | '.join(module))
        print(help_msg)
        help_msg.append('使用~help <对应模块名>查看详细信息。\n使用~modules查看所有的可用模块。\n你也可以通过查阅文档获取帮助：\nhttps://bot.teahou.se/modules/')
        if Group in kwargs:
            help_msg.append('[本消息将在一分钟后撤回]')
        send = await sendMessage(kwargs, '\n'.join(help_msg))
        if Group in kwargs:
            await asyncio.sleep(60)
            await revokeMessage(send)


async def modules_help(kwargs: dict):
    help_list = kwargs['bot_modules']['help']
    help_msg = []
    help_msg.append('当前可用的模块有：')
    module = []
    for x in help_list:
        if 'help' in help_list[x]:
            module.append(x)
    help_msg.append(' | '.join(module))
    help_msg.append('使用~help <模块名>查看详细信息。\n你也可以通过查阅文档获取帮助：\nhttps://bot.teahou.se/modules/')
    if Group in kwargs:
        help_msg.append('[本消息将在一分钟后撤回]')
    send = await sendMessage(kwargs, '\n'.join(help_msg))
    if Group in kwargs:
        await asyncio.sleep(60)
        await revokeMessage(send)


async def bot_version(kwargs: dict):
    version = os.path.abspath('.version')
    openfile = open(version, 'r')
    msg = '当前运行的代码版本号为：' + openfile.read()
    await sendMessage(kwargs, msg)
    openfile.close()


async def config_gu(kwargs):
    if Group in kwargs:
        if check_permission(kwargs):
            command = kwargs['trigger_msg'].split(' ')
            if len(command) < 3:
                await sendMessage(kwargs, '命令格式错误。')
                return
            print(command)
            if command[1] == 'add':
                await sendMessage(kwargs, database.add_group_adminuser(command[2], kwargs[Group].id))
            if command[1] == 'del':
                await sendMessage(kwargs, database.del_group_adminuser(command[2], kwargs[Group].id))


essential = {'module': config_modules, 'add_base_su': add_base_su, 'help': bot_help,
             'modules': modules_help, 'version': bot_version, 'admin_user': config_gu}
admin = {'add_su': add_su, 'del_su': del_su, 'set': set_modules, 'restart': restart_bot, 'update': update_bot,
         'echo': echo_msg, 'update&restart': update_and_restart_bot}
help = {'module': {'help': '~module <enable/disable> <模块名> - 开启/关闭一个模块', 'essential': True},
        'modules': {'help': '~modules - 查询所有可用模块。'},
        'admin_user': {'help': '~admin_user <add/del> <QQ> - 配置群内成员为机器人管理员（无需设置其为群内管理员）'}}

alias = {'enable': 'module enable', 'disable': 'module disable'}
