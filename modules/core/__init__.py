from core.loader import ModulesManager
from core.template import sendMessage
from database import BotDBUtil
from core.decorator import command


@command('module', is_base_function=True)
async def config_modules(kwargs: dict):
    """
~module <enable/disable> <module/all>"""
    command = kwargs['trigger_msg'].split(' ')
    if not len(command) > 2:
        msg = '命令格式错误。'
        await sendMessage(kwargs, msg)
        return
    do = command[1]
    command_third_word = command[2]
    if command_third_word in ModulesManager.return_modules_alias_map():
        command_third_word = ModulesManager.return_modules_alias_map()[command_third_word]
    #if not check_permission(message):
    #    await sendMessage(message, '你没有使用该命令的权限。')
    #    return
    query = BotDBUtil.Module(kwargs)
    msglist = []
    if command_third_word == 'all':
        for function in ModulesManager.return_modules_list_as_dict():
            if query.enable(function):
                msglist.append(f'成功：打开模块“{function}”')
    if do in ['enable', 'on']:
        if query.enable(command_third_word):
            msglist.append(f'成功：打开模块“{command_third_word}”')
    if do in ['disable', 'off']:
        if query.disable(command_third_word):
            msglist.append(f'成功：关闭模块“{command_third_word}”')
    if msglist is not None:
        await sendMessage(kwargs, '\n'.join(msglist))

"""
async def bot_help(message: dict):
    help_list = message['bot_modules']['help']
    alias = message['bot_modules']['alias']
    command = message['trigger_msg'].split(' ')
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
            await sendMessage(message, '\n'.join(msg))
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
            if Group in message:
                if database.check_enable_modules(message, x):
                    if 'help' in help_list[x]:
                        module.append(x)
            elif Friend in message:
                if 'help' in help_list[x]:
                    module.append(x)
        help_msg.append(' | '.join(module))
        print(help_msg)
        help_msg.append('使用~help <对应模块名>查看详细信息。\n使用~modules查看所有的可用模块。\n你也可以通过查阅文档获取帮助：\nhttps://bot.teahou.se/modules/')
        if Group in message:
            help_msg.append('[本消息将在一分钟后撤回]')
        send = await sendMessage(message, '\n'.join(help_msg))
        if Group in message:
            await asyncio.sleep(60)
            await revokeMessage(send)


async def modules_help(message: dict):
    help_list = message['bot_modules']['help']
    help_msg = []
    help_msg.append('当前可用的模块有：')
    module = []
    for x in help_list:
        if 'help' in help_list[x]:
            module.append(x)
    help_msg.append(' | '.join(module))
    help_msg.append('使用~help <模块名>查看详细信息。\n你也可以通过查阅文档获取帮助：\nhttps://bot.teahou.se/modules/')
    if Group in message:
        help_msg.append('[本消息将在一分钟后撤回]')
    send = await sendMessage(message, '\n'.join(help_msg))
    if Group in message:
        await asyncio.sleep(60)
        await revokeMessage(send)


async def bot_version(message: dict):
    version = os.path.abspath('.version')
    openfile = open(version, 'r')
    msg = '当前运行的代码版本号为：' + openfile.read()
    await sendMessage(message, msg)
    openfile.close()


async def config_gu(message):
    if Group in message:
        if check_permission(message):
            command = message['trigger_msg'].split(' ')
            if len(command) < 3:
                await sendMessage(message, '命令格式错误。')
                return
            print(command)
            if command[1] == 'add':
                await sendMessage(message, database.add_group_adminuser(command[2], message[Group].id))
            if command[1] == 'del':
                await sendMessage(message, database.del_group_adminuser(command[2], message[Group].id))


essential = {'module': config_modules, 'add_base_su': add_base_su, 'help': bot_help,
             'modules': modules_help, 'version': bot_version, 'admin_user': config_gu}
admin = {'add_su': add_su, 'del_su': del_su, 'set': set_modules, 'restart': restart_bot, 'update': update_bot,
         'echo': echo_msg, 'update&restart': update_and_restart_bot}
help = {'module': {'help': '~module <enable/disable> <模块名> - 开启/关闭一个模块', 'essential': True},
        'modules': {'help': '~modules - 查询所有可用模块。'},
        'admin_user': {'help': '~admin_user <add/del> <QQ> - 配置群内成员为机器人管理员（无需设置其为群内管理员）'}}

alias = {'enable': 'module enable', 'disable': 'module disable'}"""