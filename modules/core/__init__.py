import asyncio
import os

from core.loader import ModulesManager
from core.elements import MessageSession
from database import BotDBUtil
from core.decorator import command
from core.parser.command import CommandParser


@command('module',
         is_base_function=True,
         is_admin_function=True,
         help_doc=('module enable (<module>|all) {开启一个或所有模块}',
                   'module disable (<module>|all) {关闭一个或所有模块}'),
         alias={'enable': 'module enable', 'disable': 'module disable'}
         )
async def config_modules(msg: MessageSession):
    command_third_word = msg.parsed_msg['<module>']
    if command_third_word in ModulesManager.return_modules_alias_map():
        command_third_word = ModulesManager.return_modules_alias_map()[command_third_word]
    query = BotDBUtil.Module(msg)
    msglist = []
    if msg.parsed_msg['enable']:
        if msg.parsed_msg['all']:
            for function in ModulesManager.return_modules_list_as_dict():
                if query.enable(function):
                    msglist.append(f'成功：打开模块“{function}”')
        elif query.enable(command_third_word):
            msglist.append(f'成功：打开模块“{command_third_word}”')
    elif msg.parsed_msg['disable']:
        if msg.parsed_msg['all']:
            for function in ModulesManager.return_modules_list_as_dict():
                if query.disable(function):
                    msglist.append(f'成功：打开模块“{function}”')
        elif query.disable(command_third_word):
            msglist.append(f'成功：关闭模块“{command_third_word}”')
    if msglist is not None:
        await msg.sendMessage('\n'.join(msglist))


@command('help',
         is_base_function=True,
         help_doc=('help {查看所有可用模块}',
                   'help <module> {查看一个模块的详细信息}')
         )
async def bot_help(msg: MessageSession):
    module_list = ModulesManager.return_modules_list_as_dict()
    alias = ModulesManager.return_modules_alias_map()
    if msg.parsed_msg is not None:
        msgs = []
        help_name = msg.parsed_msg['<module>']
        if help_name in alias:
            help_name = alias[help_name]
        if help_name in module_list:
            help_ = CommandParser(module_list[help_name].help_doc).return_formatted_help_doc()
            if help_ is not None:
                msgs.append(help_)
        if msgs:
            await msg.sendMessage('\n'.join(msgs))
    else:
        help_msg = ['基础命令：']
        essential = []
        for x in module_list:
            if module_list[x].is_base_function:
                essential.append(module_list[x].bind_prefix)
        help_msg.append(' | '.join(essential))
        help_msg.append('模块扩展命令：')
        module = []
        for x in module_list:
            if BotDBUtil.Module(msg).check_target_enabled_module(module_list[x].bind_prefix):
                module.append(x)
        help_msg.append(' | '.join(module))
        print(help_msg)
        help_msg.append('使用~help <对应模块名>查看详细信息。\n使用~modules查看所有的可用模块。\n你也可以通过查阅文档获取帮助：\nhttps://bot.teahou.se/modules/')
        help_msg.append('[本消息将在一分钟后撤回]')
        send = await msg.sendMessage('\n'.join(help_msg))
        await asyncio.sleep(60)
        await send.delete()


@command('modules',
         is_base_function=True,
         help_doc='modules {查看所有可用模块}'
         )
async def modules_help(msg: MessageSession):
    module_list = ModulesManager.return_modules_list_as_dict()
    help_msg = ['当前可用的模块有：']
    module = []
    for x in module_list:
        module.append(module_list[x].bind_prefix)
    help_msg.append(' | '.join(module))
    help_msg.append('使用~help <模块名>查看详细信息。\n你也可以通过查阅文档获取帮助：\nhttps://bot.teahou.se/modules/')
    help_msg.append('[本消息将在一分钟后撤回]')
    send = await msg.sendMessage('\n'.join(help_msg))
    await asyncio.sleep(60)
    await send.delete()


@command('version',
         is_base_function=True,
         help_doc='version {查看机器人的版本号}'
         )
async def bot_version(msg: MessageSession):
    version = os.path.abspath('.version')
    openfile = open(version, 'r')
    msgs = '当前运行的代码版本号为：' + openfile.read()
    await msg.sendMessage(msgs, msgs)
    openfile.close()


@command('admin',
         is_base_function=True,
         is_admin_function=True,
         help_doc=('admin add <user>', 'admin del <user>')
         )
async def config_gu(msg: MessageSession):
    if msg.parsed_msg['add']:
        user = msg.parsed_msg['<user>']
        if user:
            if BotDBUtil.SenderInfo(f"{msg.target.senderFrom}|{user}").add_TargetAdmin(msg.target.targetId):
                await msg.sendMessage("成功")
    if msg.parsed_msg['del']:
        user = msg.parsed_msg['<user>']
        if user:
            if BotDBUtil.SenderInfo(f"{msg.target.senderFrom}|{user}").remove_TargetAdmin(msg.target.targetId):
                await msg.sendMessage("成功")