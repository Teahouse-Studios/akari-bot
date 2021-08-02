import asyncio
import os
import psutil
import time

from core.loader import ModulesManager
from core.elements import MessageSession
from database import BotDBUtil
from core.loader.decorator import command
from core.parser.command import CommandParser


@command('module',
         is_base_function=True,
         need_admin=True,
         help_doc=('~module enable (<module>...|all) {开启一个/多个或所有模块}',
                   '~module disable (<module>...|all) {关闭一个/多个或所有模块}'),
         alias={'enable': 'module enable', 'disable': 'module disable'}
         )
async def config_modules(msg: MessageSession):
    alias = ModulesManager.return_modules_alias_map()
    modules = ModulesManager.return_modules_list_as_dict()
    wait_config = msg.parsed_msg['<module>']
    wait_config_list = []
    for module in wait_config:
        if module not in wait_config_list:
            if module in alias:
                wait_config_list.append(alias[module])
            else:
                wait_config_list.append(module)
    query = BotDBUtil.Module(msg)
    msglist = []
    for x in wait_config_list:
        if x not in modules:
            msglist.append(f'失败：“{x}”模块不存在')
            wait_config_list.remove(x)
    if msg.parsed_msg['enable']:
        if msg.parsed_msg['all']:
            for function in modules:
                if query.enable(function):
                    msglist.append(f'成功：打开模块“{function}”')
        else:
            if query.enable(wait_config_list):
                for module in wait_config_list:
                    msglist.append(f'成功：打开模块“{module}”')
    elif msg.parsed_msg['disable']:
        if msg.parsed_msg['all']:
            for function in modules:
                if query.disable(function):
                    msglist.append(f'成功：关闭模块“{function}”')
        else:
            if query.disable(wait_config_list):
                for module in wait_config_list:
                    msglist.append(f'成功：关闭模块“{module}”')
    if msglist is not None:
        await msg.sendMessage('\n'.join(msglist))


@command('help',
         is_base_function=True,
         help_doc=('~help {查看所有可用模块}',
                   '~help <module> {查看一个模块的详细信息}')
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
         help_doc='~modules {查看所有可用模块}'
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
         help_doc='~version {查看机器人的版本号}'
         )
async def bot_version(msg: MessageSession):
    version = os.path.abspath('.version')
    tag = os.path.abspath('.version_tag')
    open_version = open(version, 'r')
    open_tag = open(tag, 'r')
    msgs = f'当前运行的代码版本号为：{open_tag.read()}（{open_version.read()}）'
    await msg.sendMessage(msgs, msgs)
    open_version.close()


@command('ping',
         is_base_function=True,
         help_doc='~ping {获取机器人信息}'
         )
async def ping(msg: MessageSession):
    checkpermisson = msg.checkSuperUser()
    result = "Pong!"
    if checkpermisson:
        Boot_Start = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(psutil.boot_time()))
        time.sleep(0.5)
        Cpu_usage = psutil.cpu_percent()
        RAM = int(psutil.virtual_memory().total / (1024 * 1024))
        RAM_percent = psutil.virtual_memory().percent
        Swap = int(psutil.swap_memory().total / (1024 * 1024))
        Swap_percent = psutil.swap_memory().percent
        Disk = int(psutil.disk_usage('/').used / (1024 * 1024 * 1024))
        DiskTotal = int(psutil.disk_usage('/').total / (1024 * 1024 * 1024))
        """
        try:
            GroupList = len(await app.groupList())
        except Exception:
            GroupList = '无法获取'
        try:
            FriendList = len(await app.friendList())
        except Exception:
            FriendList = '无法获取'
        """
        BFH = r'%'
        result += (f"\n系统运行时间：{Boot_Start}"
                   + f"\n当前CPU使用率：{Cpu_usage}{BFH}"
                   + f"\n物理内存：{RAM}M 使用率：{RAM_percent}{BFH}"
                   + f"\nSwap内存：{Swap}M 使用率：{Swap_percent}{BFH}"
                   + f"\n磁盘容量：{Disk}G/{DiskTotal}G"
                   #+ f"\n已加入QQ群聊：{GroupList}"
                   #+ f" | 已添加QQ好友：{FriendList}" """
        )
    await msg.sendMessage(result)


@command('admin',
         is_base_function=True,
         need_admin=True,
         help_doc=('~admin add <user>', '~admin del <user>')
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
