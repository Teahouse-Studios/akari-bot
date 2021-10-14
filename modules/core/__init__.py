import asyncio
import os
import sys
import time

import psutil
import ujson as json

from core.elements import MessageSession, Command
from core.loader import ModulesManager
from core.decorator import on_command
from core.parser.command import CommandParser, InvalidHelpDocTypeError
from core.utils import PrivateAssets
from database import BotDBUtil


@on_command('module',
            is_base_function=True,
            need_admin=True,
            help_doc=('~module enable (<module>...|all) {开启一个/多个或所有模块}',
                   '~module disable (<module>...|all) {关闭一个/多个或所有模块}'),
            alias={'enable': 'module enable', 'disable': 'module disable'},
            developers=['OasisAkari'], allowed_none=False
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
    recommend_modules_list = []
    if msg.parsed_msg['enable']:
        enable_list = []
        if wait_config_list == ['all']:
            for function in modules:
                if not modules[function].need_superuser:
                    if isinstance(modules[function], Command) and modules[function].is_base_function:
                        continue
                    enable_list.append(function)
        else:
            for module in wait_config_list:
                if module not in modules:
                    msglist.append(f'失败：“{module}”模块不存在')
                else:
                    if modules[module].need_superuser and not msg.checkSuperUser():
                        msglist.append(f'失败：你没有打开“{module}”的权限。')
                    elif isinstance(modules[module], Command) and modules[module].is_base_function:
                        msglist.append(f'失败：“{module}”为基础模块。')
                    else:
                        enable_list.append(module)
                        recommend = modules[module].recommend_modules
                        if isinstance(recommend, str):
                            recommend_modules_list.append(recommend)
                        if isinstance(recommend, (list, tuple)):
                            for r in recommend:
                                recommend_modules_list.append(r)
        if query.enable(enable_list):
            for x in enable_list:
                msglist.append(f'成功：打开模块“{x}”')
    elif msg.parsed_msg['disable']:
        disable_list = []
        if wait_config_list == ['all']:
            for function in modules:
                if not modules[function].need_superuser and not modules[function].is_base_function:
                    disable_list.append(function)
        else:
            for module in wait_config_list:
                if module not in modules:
                    msglist.append(f'失败：“{module}”模块不存在')
                else:
                    disable_list.append(module)
        if query.disable(disable_list):
            for x in disable_list:
                msglist.append(f'成功：关闭模块“{x}”')
    if msglist is not None:
        await msg.sendMessage('\n'.join(msglist))
    if recommend_modules_list:
        fmt_help_doc_list = []
        for m in recommend_modules_list:
            try:
                hdoc = CommandParser(modules[m]).return_formatted_help_doc()
                fmt_help_doc_list.append(f'模块{m}的帮助信息：\n' + hdoc)
            except InvalidHelpDocTypeError:
                pass
        confirm = await msg.waitConfirm('建议同时打开以下模块：\n' +
                                        '\n'.join(recommend_modules_list) + '\n\n' +
                                        '\n'.join(fmt_help_doc_list) +
                                        '\n是否一并打开？')
        if confirm:
            if query.enable(recommend_modules_list):
                msglist = []
                for x in recommend_modules_list:
                    msglist.append(f'成功：打开模块“{x}”')
                await msg.sendMessage('\n'.join(msglist))


@on_command('help',
            is_base_function=True,
            help_doc=('~help {查看所有可用模块}',
                   '~help <module> {查看一个模块的详细信息}'),
            developers=['OasisAkari', 'Dianliang233'],
            )
async def bot_help(msg: MessageSession):
    module_list = ModulesManager.return_modules_list_as_dict()
    developers = ModulesManager.return_modules_developers_map()
    alias = ModulesManager.return_modules_alias_map()
    modules_alias = ModulesManager.return_modules_alias_list()
    if msg.parsed_msg is not None:
        msgs = []
        help_name = msg.parsed_msg['<module>']
        if help_name in alias:
            help_name = alias[help_name]
        if help_name in module_list:
            help_ = CommandParser(module_list[help_name]).return_formatted_help_doc()
            if help_ is not None:
                msgs.append(help_)
        if msgs:
            doc = '\n'.join(msgs)
            if help_name in modules_alias:
                malias = []
                for a in modules_alias[help_name]:
                    if isinstance(modules_alias[help_name][a], dict):
                        malias.append(f'{a} -> {modules_alias[help_name][a]}')
                    elif isinstance(modules_alias[help_name][a], str):
                        malias.append(f'{a} -> {help_name}')
                    else:
                        malias.append('<数据类型错误，请联系开发者解决>')
                if malias:
                    doc += '\n命令别名：\n' + '\n'.join(malias)
            if help_name in developers:
                dev_list = developers[help_name]
                if isinstance(dev_list, (list, tuple)):
                    devs = '、'.join(developers[help_name]) if developers[help_name] is not None else ''
                elif isinstance(dev_list, str):
                    devs = dev_list
                else:
                    devs = '<数据类型错误，请联系开发者解决>'
            else:
                devs = ''
            devs_msg = '\n模块作者：' + devs if devs != '' else ''
            await msg.sendMessage(doc + devs_msg)
    else:
        help_msg = ['基础命令：']
        essential = []
        for x in module_list:
            if isinstance(module_list[x], Command) and module_list[x].is_base_function:
                essential.append(module_list[x].bind_prefix)
        help_msg.append(' | '.join(essential))
        help_msg.append('模块扩展命令：')
        module = []
        for x in module_list:
            if x in BotDBUtil.Module(msg).check_target_enabled_module_list():
                module.append(x)
        help_msg.append(' | '.join(module))
        print(help_msg)
        help_msg.append(
            '使用~help <对应模块名>查看详细信息。\n使用~modules查看所有的可用模块。\n你也可以通过查阅文档获取帮助：\nhttps://bot.teahou.se/wiki/')
        help_msg.append('[本消息将在一分钟后撤回]')
        send = await msg.sendMessage('\n'.join(help_msg))
        await asyncio.sleep(60)
        await send.delete()


@on_command('modules',
            is_base_function=True,
            help_doc='~modules {查看所有可用模块}',
            developers=['OasisAkari']
            )
async def modules_help(msg: MessageSession):
    module_list = ModulesManager.return_modules_list_as_dict()
    help_msg = ['当前可用的模块有：']
    module = []
    for x in module_list:
        if x[0] == '_':
            continue
        if isinstance(module_list[x], Command) and module_list[x].is_base_function and module_list[x].need_superuser:
            continue
        module.append(module_list[x].bind_prefix)
    help_msg.append(' | '.join(module))
    help_msg.append(
        '使用~help <模块名>查看详细信息。\n你也可以通过查阅文档获取帮助：\nhttps://bot.teahou.se/wiki/')
    help_msg.append('[本消息将在一分钟后撤回]')
    send = await msg.sendMessage('\n'.join(help_msg))
    await asyncio.sleep(60)
    await send.delete()


@on_command('version',
            is_base_function=True,
            help_doc='~version {查看机器人的版本号}',
            developers=['OasisAkari', 'Dianliang233']
            )
async def bot_version(msg: MessageSession):
    version = os.path.abspath(PrivateAssets.path + '/version')
    tag = os.path.abspath(PrivateAssets.path + '/version_tag')
    open_version = open(version, 'r')
    open_tag = open(tag, 'r')
    msgs = f'当前运行的代码版本号为：{open_tag.read()}（{open_version.read()}）'
    await msg.sendMessage(msgs, msgs)
    open_version.close()


@on_command('ping',
            is_base_function=True,
            help_doc='~ping {获取机器人信息}',
            developers=['OasisAkari']
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
                   # + f"\n已加入QQ群聊：{GroupList}"
                   # + f" | 已添加QQ好友：{FriendList}" """
                   )
    await msg.sendMessage(result)


@on_command('admin',
            is_base_function=True,
            need_admin=True,
            help_doc=('~admin add <UserID> {设置成员为机器人管理员}', '~admin del <UserID> {取消成员的机器人管理员}'),
            developers=['OasisAkari'], allowed_none=False
            )
async def config_gu(msg: MessageSession):
    if msg.parsed_msg['add']:
        user = msg.parsed_msg['<UserID>']
        if user and not BotDBUtil.SenderInfo(f"{msg.target.senderFrom}|{user}").check_TargetAdmin(msg.target.targetId):
            if BotDBUtil.SenderInfo(f"{msg.target.senderFrom}|{user}").add_TargetAdmin(msg.target.targetId):
                await msg.sendMessage("成功")
    if msg.parsed_msg['del']:
        user = msg.parsed_msg['<UserID>']
        if user:
            if BotDBUtil.SenderInfo(f"{msg.target.senderFrom}|{user}").remove_TargetAdmin(msg.target.targetId):
                await msg.sendMessage("成功")


@on_command('add_su', developers=['OasisAkari'], need_superuser=True, help_doc='add_su <user>')
async def add_su(message: MessageSession):
    user = message.parsed_msg['<user>']
    print(message.parsed_msg)
    if user:
        if BotDBUtil.SenderInfo(user).edit('isSuperUser', True):
            await message.sendMessage('成功')


@on_command('del_su', developers=['OasisAkari'], need_superuser=True, help_doc='del_su <user>')
async def del_su(message: MessageSession):
    user = message.parsed_msg['<user>']
    if user:
        if BotDBUtil.SenderInfo(user).edit('isSuperUser', False):
            await message.sendMessage('成功')


"""
@on_command('set_modules', need_superuser=True, help_doc='set_modules <>')
async def set_modules(display_msg: dict):
    ...
"""


@on_command('restart', developers=['OasisAkari'], need_superuser=True)
async def restart_bot(msg: MessageSession):
    await msg.sendMessage('你确定吗？')
    confirm = await msg.waitConfirm()
    if confirm:
        update = os.path.abspath(PrivateAssets.path + '/cache_restart_author')
        write_version = open(update, 'w')
        write_version.write(json.dumps({'From': msg.target.targetFrom, 'ID': msg.target.targetId}))
        write_version.close()
        await msg.sendMessage('已执行。')
        python = sys.executable
        os.execl(python, python, *sys.argv)


@on_command('update', developers=['OasisAkari'], need_superuser=True)
async def update_bot(msg: MessageSession):
    await msg.sendMessage('你确定吗？')
    confirm = await msg.waitConfirm()
    if confirm:
        result = os.popen('git pull', 'r')
        await msg.sendMessage(result.read()[:-1])


@on_command('update&restart', developers=['OasisAkari'], need_superuser=True)
async def update_and_restart_bot(msg: MessageSession):
    await msg.sendMessage('你确定吗？')
    confirm = await msg.waitConfirm()
    if confirm:
        update = os.path.abspath(PrivateAssets.path + '/cache_restart_author')
        write_version = open(update, 'w')
        write_version.write(json.dumps({'From': msg.target.targetFrom, 'ID': msg.target.targetId}))
        write_version.close()
        result = os.popen('git pull', 'r')
        await msg.sendMessage(result.read()[:-1])
        python = sys.executable
        os.execl(python, python, *sys.argv)


@on_command('echo', developers=['OasisAkari'], need_superuser=True, help_doc='echo <display_msg>')
async def echo_msg(msg: MessageSession):
    await msg.sendMessage(msg.parsed_msg['<display_msg>'])
