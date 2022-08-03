import asyncio
import os
import platform
import sys
import time
import traceback
from datetime import datetime, timedelta

import matplotlib.pyplot as plt
import numpy as np
import psutil
import ujson as json
from cpuinfo import get_cpu_info

from config import Config
from core.builtins.message import MessageSession
from core.component import on_command
from core.elements import Command, PrivateAssets, Image, Plain, ExecutionLockList
from core.loader import ModulesManager
from core.parser.command import CommandParser, InvalidHelpDocTypeError
from core.parser.message import remove_temp_ban
from core.tos import pardon_user, warn_user
from core.utils.cache import random_cache_path
from core.utils.image_table import ImageTable, image_table_render, web_render
from core.utils.tasks import MessageTaskManager
from database import BotDBUtil

module = on_command('module',
                    base=True,
                    alias={'enable': 'module enable', 'disable': 'module disable'},
                    developers=['OasisAkari'],
                    required_admin=True
                    )


@module.handle(['enable (<module>...|all) {开启一个/多个或所有模块}',
                'disable (<module>...|all) {关闭一个/多个或所有模块}',
                'list {查看所有可用模块}'], exclude_from=['QQ|Guild'])
async def _(msg: MessageSession):
    if msg.parsed_msg['list']:
        await modules_help(msg)
    await config_modules(msg)


@module.handle(['enable (<module>...|all) [-g] {开启一个/多个或所有模块}',
                'disable (<module>...|all) [-g] {关闭一个/多个或所有模块\n [-g] - 为文字频道内全局操作}',
                'list {查看所有可用模块}'],
               available_for=['QQ|Guild'])
async def _(msg: MessageSession):
    if msg.parsed_msg['list']:
        await modules_help(msg)
    await config_modules(msg)


async def config_modules(msg: MessageSession):
    alias = ModulesManager.return_modules_alias_map()
    modules_ = ModulesManager.return_modules_list_as_dict(targetFrom=msg.target.targetFrom)
    enabled_modules_list = BotDBUtil.Module(msg).check_target_enabled_module_list()
    wait_config = msg.parsed_msg['<module>']
    wait_config_list = []
    for module_ in wait_config:
        if module_ not in wait_config_list:
            if module_ in alias:
                wait_config_list.append(alias[module_])
            else:
                wait_config_list.append(module_)
    query = BotDBUtil.Module(msg)
    msglist = []
    recommend_modules_list = []
    recommend_modules_help_doc_list = []
    if msg.parsed_msg['enable']:
        enable_list = []
        if wait_config_list == ['all']:
            for function in modules_:
                if function[0] == '_':
                    continue
                if isinstance(modules_[function], Command) and (
                    modules_[function].base or modules_[function].required_superuser):
                    continue
                enable_list.append(function)
        else:
            for module_ in wait_config_list:
                if module_ not in modules_:
                    msglist.append(f'失败：“{module_}”模块不存在')
                else:
                    if modules_[module_].required_superuser and not msg.checkSuperUser():
                        msglist.append(f'失败：你没有打开“{module_}”的权限。')
                    elif isinstance(modules_[module_], Command) and modules_[module_].base:
                        msglist.append(f'失败：“{module_}”为基础模块。')
                    else:
                        enable_list.append(module_)
                        recommend = modules_[module_].recommend_modules
                        if recommend is not None:
                            for r in recommend:
                                if r not in enable_list and r not in enabled_modules_list:
                                    recommend_modules_list.append(r)
        if '-g' in msg.parsed_msg and msg.parsed_msg['-g']:
            get_all_channel = await msg.get_text_channel_list()
            for x in get_all_channel:
                query = BotDBUtil.Module(f'{msg.target.targetFrom}|{x}')
                query.enable(enable_list)
            for x in enable_list:
                msglist.append(f'成功：为所有文字频道打开“{x}”模块')
        else:
            if query.enable(enable_list):
                for x in enable_list:
                    if x in enabled_modules_list:
                        msglist.append(f'失败：“{x}”模块已经开启')
                    else:
                        msglist.append(f'成功：打开模块“{x}”')
        if recommend_modules_list:
            for m in recommend_modules_list:
                try:
                    hdoc = CommandParser(modules_[m], msg=msg,
                                         command_prefixes=msg.prefixes).return_formatted_help_doc()
                    recommend_modules_help_doc_list.append(f'模块{m}的帮助信息：')
                    if modules_[m].desc is not None:
                        recommend_modules_help_doc_list.append(modules_[m].desc)
                    recommend_modules_help_doc_list.append(hdoc)
                except InvalidHelpDocTypeError:
                    pass
    elif msg.parsed_msg['disable']:
        disable_list = []
        if wait_config_list == ['all']:
            for function in modules_:
                if function[0] == '_':
                    continue
                if isinstance(modules_[function], Command) and (
                    modules_[function].base or modules_[function].required_superuser):
                    continue
                disable_list.append(function)
        else:
            for module_ in wait_config_list:
                if module_ not in modules_:
                    msglist.append(f'失败：“{module_}”模块不存在')
                else:
                    if modules_[module_].required_superuser and not msg.checkSuperUser():
                        msglist.append(f'失败：你没有关闭“{module_}”的权限。')
                    elif isinstance(modules_[module_], Command) and modules_[module_].base:
                        msglist.append(f'失败：“{module_}”为基础模块，无法关闭。')
                    else:
                        disable_list.append(module_)
        if '-g' in msg.parsed_msg and msg.parsed_msg['-g']:
            get_all_channel = await msg.get_text_channel_list()
            for x in get_all_channel:
                query = BotDBUtil.Module(f'{msg.target.targetFrom}|{x}')
                query.disable(disable_list)
            for x in disable_list:
                msglist.append(f'成功：为所有文字频道关闭“{x}”模块')
        else:
            if query.disable(disable_list):
                for x in disable_list:
                    if x not in enabled_modules_list:
                        msglist.append(f'失败：“{x}”模块已经关闭')
                    else:
                        msglist.append(f'成功：关闭模块“{x}”')
    if msglist is not None:
        if not recommend_modules_help_doc_list:
            await msg.finish('\n'.join(msglist))
        else:
            await msg.sendMessage('\n'.join(msglist))
    if recommend_modules_help_doc_list and ('-g' not in msg.parsed_msg or not msg.parsed_msg['-g']):
        confirm = await msg.waitConfirm('建议同时打开以下模块：\n' +
                                        '\n'.join(recommend_modules_list) + '\n\n' +
                                        '\n'.join(recommend_modules_help_doc_list) +
                                        '\n是否一并打开？')
        if confirm:
            query = BotDBUtil.Module(msg)
            if query.enable(recommend_modules_list):
                msglist = []
                for x in recommend_modules_list:
                    msglist.append(f'成功：打开模块“{x}”')
                await msg.finish('\n'.join(msglist))
    else:
        await msg.finish()


hlp = on_command('help',
                 base=True,
                 developers=['OasisAkari', 'Dianliang233'],
                 )


@hlp.handle('<module> {查看一个模块的详细信息}')
async def bot_help(msg: MessageSession):
    module_list = ModulesManager.return_modules_list_as_dict(targetFrom=msg.target.targetFrom)
    developers = ModulesManager.return_modules_developers_map()
    alias = ModulesManager.return_modules_alias_map()
    if msg.parsed_msg is not None:
        msgs = []
        help_name = msg.parsed_msg['<module>']
        if help_name in alias:
            help_name = alias[help_name]
        if help_name in module_list:
            module_ = module_list[help_name]
            if module_.desc is not None:
                msgs.append(module_.desc)
            help_ = CommandParser(module_list[help_name], msg=msg, command_prefixes=msg.prefixes)
            if help_.args is not None:
                msgs.append(help_.return_formatted_help_doc())
        if msgs:
            doc = '\n'.join(msgs)
            module_alias = ModulesManager.return_module_alias(help_name)
            malias = []
            for a in module_alias:
                malias.append(f'{a} -> {module_alias[a]}')
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
            await msg.finish(doc + devs_msg)
        else:
            await msg.finish('此模块可能不存在，请检查输入。')


@hlp.handle()
async def _(msg: MessageSession):
    module_list = ModulesManager.return_modules_list_as_dict(targetFrom=msg.target.targetFrom)
    target_enabled_list = BotDBUtil.Module(msg).check_target_enabled_module_list()
    developers = ModulesManager.return_modules_developers_map()
    legacy_help = True
    if web_render and msg.Feature.image:
        try:
            tables = []
            essential = []
            m = []
            for x in module_list:
                module_ = module_list[x]
                appends = [module_.bind_prefix]
                help_ = CommandParser(module_, msg=msg, command_prefixes=msg.prefixes)
                doc_ = []
                if module_.desc is not None:
                    doc_.append(module_.desc)
                if help_.args is not None:
                    doc_.append(help_.return_formatted_help_doc())
                doc = '\n'.join(doc_)
                appends.append(doc)
                module_alias = ModulesManager.return_module_alias(module_.bind_prefix)
                malias = []
                for a in module_alias:
                    malias.append(f'{a} -> {module_alias[a]}')
                appends.append('\n'.join(malias) if malias else '')
                appends.append('、'.join(developers[x]) if developers.get(x) is not None else '')
                if isinstance(module_, Command) and module_.base:
                    essential.append(appends)
                if x in target_enabled_list:
                    m.append(appends)
            if essential:
                tables.append(ImageTable(essential, ['基础模块列表', '帮助信息', '命令别名', '作者']))
            if m:
                tables.append(ImageTable(m, ['扩展模块列表', '帮助信息', '命令别名', '作者']))
            if tables:
                render = await image_table_render(tables)
                if render:
                    legacy_help = False
                    await msg.finish([Image(render),
                                      Plain(f'此处展示的帮助文档仅展示已开启的模块，若需要查看全部模块的帮助文档，请使用{msg.prefixes[0]}module list命令。'
                                            '\n你也可以通过查阅文档获取帮助：'
                                            '\nhttps://bot.teahouse.team/wiki/'
                                            '\n若您有经济实力，欢迎给孩子们在爱发电上打钱：'
                                            '\nhttps://afdian.net/@teahouse')])
        except Exception:
            traceback.print_exc()
    if legacy_help:
        help_msg = ['基础命令：']
        essential = []
        for x in module_list:
            if isinstance(module_list[x], Command) and module_list[x].base:
                essential.append(module_list[x].bind_prefix)
        help_msg.append(' | '.join(essential))
        help_msg.append('模块扩展命令：')
        module_ = []
        for x in module_list:
            if x in target_enabled_list:
                module_.append(x)
        help_msg.append(' | '.join(module_))
        print(help_msg)
        help_msg.append(
            f'使用{msg.prefixes[0]}help <对应模块名>查看详细信息。\n使用{msg.prefixes[0]}module list查看所有的可用模块。\n你也可以通过查阅文档获取帮助：\nhttps://bot.teahouse.team/wiki/')
        if msg.Feature.delete:
            help_msg.append('[本消息将在一分钟后撤回]')
        send = await msg.sendMessage('\n'.join(help_msg))
        await msg.sleep(60)
        await send.delete()


async def modules_help(msg: MessageSession):
    module_list = ModulesManager.return_modules_list_as_dict(targetFrom=msg.target.targetFrom)
    developers = ModulesManager.return_modules_developers_map()
    legacy_help = True
    if web_render and msg.Feature.image:
        try:
            tables = []
            m = []
            for x in module_list:
                module_ = module_list[x]
                if x[0] == '_':
                    continue
                if isinstance(module_, Command) and (module_.base or module_.required_superuser):
                    continue
                appends = [module_.bind_prefix]
                help_ = CommandParser(module_, command_prefixes=msg.prefixes)
                doc_ = []
                if module_.desc is not None:
                    doc_.append(module_.desc)
                if help_.args is not None:
                    doc_.append(help_.return_formatted_help_doc())
                doc = '\n'.join(doc_)
                appends.append(doc)
                module_alias = ModulesManager.return_module_alias(module_.bind_prefix)
                malias = []
                for a in module_alias:
                    malias.append(f'{a} -> {module_alias[a]}')
                appends.append('\n'.join(malias) if malias else '')
                appends.append('、'.join(developers[x]) if developers.get(x) is not None else '')
                m.append(appends)
            if m:
                tables.append(ImageTable(m, ['扩展模块列表', '帮助信息', '命令别名', '作者']))
            if tables:
                render = await image_table_render(tables)
                if render:
                    legacy_help = False
                    await msg.finish([Image(render)])
        except Exception:
            traceback.print_exc()
    if legacy_help:
        help_msg = ['当前可用的模块有：']
        module_ = []
        for x in module_list:
            if x[0] == '_':
                continue
            if isinstance(module_list[x], Command) and (module_list[x].base or module_list[x].required_superuser):
                continue
            module_.append(module_list[x].bind_prefix)
        help_msg.append(' | '.join(module_))
        help_msg.append(
            '使用~help <模块名>查看详细信息。\n你也可以通过查阅文档获取帮助：\nhttps://bot.teahouse.team/wiki/')
        if msg.Feature.delete:
            help_msg.append('[本消息将在一分钟后撤回]')
        send = await msg.sendMessage('\n'.join(help_msg))
        await msg.sleep(60)
        await send.delete()


p = on_command('prefix', required_admin=True, base=True)


@p.handle('add <prefix> {设置自定义机器人命令前缀}', 'remove <prefix> {移除自定义机器人命令前缀}', 'reset {重置自定义机器人命令前缀}')
async def set_prefix(msg: MessageSession):
    options = BotDBUtil.Options(msg)
    prefixes = options.get('command_prefix')
    arg1 = msg.parsed_msg['<prefix>']
    if prefixes is None:
        prefixes = []
    if msg.parsed_msg['add']:
        if arg1 not in prefixes:
            prefixes.append(arg1)
            options.edit('command_prefix', prefixes)
            await msg.sendMessage(f'已添加自定义命令前缀：{arg1}\n帮助文档将默认使用该前缀进行展示。')
        else:
            await msg.sendMessage(f'此命令前缀已存在于自定义前缀列表。')
    elif msg.parsed_msg['remove']:
        if arg1 in prefixes:
            prefixes.remove(arg1)
            options.edit('command_prefix', prefixes)
            await msg.sendMessage(f'已移除自定义命令前缀：{arg1}')
        else:
            await msg.sendMessage(f'此命令前缀不存在于自定义前缀列表。')
    elif msg.parsed_msg['reset']:
        options.edit('command_prefix', [])
        await msg.sendMessage('已重置自定义命令前缀列表。')


ali = on_command('alias', required_admin=True, base=True)


@ali.handle('add <alias> <command> {添加自定义命令别名}', 'remove <alias> {移除自定义命令别名}', 'reset {重置自定义命令别名}')
async def set_alias(msg: MessageSession):
    options = BotDBUtil.Options(msg)
    alias = options.get('command_alias')
    arg1 = msg.parsed_msg['<alias>']
    arg2 = msg.parsed_msg['<command>']
    if alias is None:
        alias = {}
    if msg.parsed_msg['add']:
        if arg1 not in alias:
            has_prefix = False
            for prefixes in msg.prefixes:
                if arg2.startswith(prefixes):
                    has_prefix = True
                    break
            if not has_prefix:
                await msg.sendMessage(f'添加的别名对应的命令必须以命令前缀开头，请检查。')
                return
            alias[arg1] = arg2
            options.edit('command_alias', alias)
            await msg.sendMessage(f'已添加自定义命令别名：{arg1} -> {arg2}')
        else:
            await msg.sendMessage(f'[{arg1}]别名已存在于自定义别名列表。')
    elif msg.parsed_msg['remove']:
        if arg1 in alias:
            del alias[arg1]
            options.edit('command_alias', alias)
            await msg.sendMessage(f'已移除自定义命令别名：{arg1}')
        else:
            await msg.sendMessage(f'[{arg1}]别名不存在于自定义别名列表。')
    elif msg.parsed_msg['reset']:
        options.edit('command_alias', {})
        await msg.sendMessage('已重置自定义命令别名列表。')


version = on_command('version',
                     base=True,
                     desc='查看机器人的版本号',
                     developers=['OasisAkari', 'Dianliang233']
                     )


@version.handle()
async def bot_version(msg: MessageSession):
    ver = os.path.abspath(PrivateAssets.path + '/version')
    tag = os.path.abspath(PrivateAssets.path + '/version_tag')
    open_version = open(ver, 'r')
    open_tag = open(tag, 'r')
    msgs = f'当前运行的代码版本号为：{open_tag.read()}（{open_version.read()}）'
    open_version.close()
    await msg.finish(msgs, msgs)


ping = on_command('ping',
                  base=True,
                  desc='获取机器人状态',
                  developers=['OasisAkari']
                  )

started_time = datetime.now()


@ping.handle()
async def _(msg: MessageSession):
    checkpermisson = msg.checkSuperUser()
    result = "Pong!"
    if checkpermisson:
        timediff = str(datetime.now() - started_time)
        Boot_Start = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(psutil.boot_time()))
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
                   + f"\n机器人已运行：{timediff}"
                   + f"\nPython版本：{platform.python_version()}"
                   + f"\n处理器型号：{get_cpu_info()['brand_raw']}"
                   + f"\n当前处理器使用率：{Cpu_usage}{BFH}"
                   + f"\n物理内存：{RAM}M 使用率：{RAM_percent}{BFH}"
                   + f"\nSwap内存：{Swap}M 使用率：{Swap_percent}{BFH}"
                   + f"\n磁盘容量：{Disk}G/{DiskTotal}G"
                   # + f"\n已加入QQ群聊：{GroupList}"
                   # + f" | 已添加QQ好友：{FriendList}" """
                   )
    await msg.finish(result)


admin = on_command('admin',
                   base=True,
                   required_admin=True,
                   developers=['OasisAkari'],
                   desc='用于设置成员为机器人管理员，实现不设置成员为群聊管理员的情况下管理机器人的功能。已是群聊管理员无需设置此项目。'
                   )


@admin.handle(['add <UserID> {设置成员为机器人管理员}', 'del <UserID> {取消成员的机器人管理员}'])
async def config_gu(msg: MessageSession):
    user = msg.parsed_msg['<UserID>']
    if not user.startswith(f'{msg.target.senderFrom}|'):
        await msg.finish(f'ID格式错误，请对象使用{msg.prefixes[0]}whoami命令查看用户ID。')
    if msg.parsed_msg['add']:
        if user and not BotDBUtil.SenderInfo(user).check_TargetAdmin(msg.target.targetId):
            if BotDBUtil.SenderInfo(user).add_TargetAdmin(msg.target.targetId):
                await msg.finish("成功")
        else:
            await msg.finish("此成员已经是机器人管理员。")
    if msg.parsed_msg['del']:
        if user:
            if BotDBUtil.SenderInfo(user).remove_TargetAdmin(msg.target.targetId):
                await msg.finish("成功")


su = on_command('superuser', alias=['su'], developers=['OasisAkari', 'Dianliang233'], required_superuser=True)


@su.handle('add <user>')
async def add_su(message: MessageSession):
    user = message.parsed_msg['<user>']
    if not user.startswith(f'{message.target.senderFrom}|'):
        await message.finish(f'ID格式错误，请对象使用{message.prefixes[0]}whoami命令查看用户ID。')
    if user:
        if BotDBUtil.SenderInfo(user).edit('isSuperUser', True):
            await message.finish('操作成功：已将' + user + '设置为超级用户。')


@su.handle('del <user>')
async def del_su(message: MessageSession):
    user = message.parsed_msg['<user>']
    if not user.startswith(f'{message.target.senderFrom}|'):
        await message.finish(f'ID格式错误，请对象使用{message.prefixes[0]}whoami命令查看用户ID。')
    if user:
        if BotDBUtil.SenderInfo(user).edit('isSuperUser', False):
            await message.finish('操作成功：已将' + user + '移出超级用户。')


whoami = on_command('whoami', developers=['Dianliang233'], desc='获取发送命令的账号在机器人内部的 ID', base=True)


@whoami.handle()
async def _(msg: MessageSession):
    rights = ''
    if await msg.checkNativePermission():
        rights += '\n（你拥有本对话的管理员权限）'
    elif await msg.checkPermission():
        rights += '\n（你拥有本对话的机器人管理员权限）'
    if msg.checkSuperUser():
        rights += '\n（你拥有本机器人的超级用户权限）'
    await msg.finish(f'你的 ID 是：{msg.target.senderId}\n本对话的 ID 是：{msg.target.targetId}' + rights,
                     disable_secret_check=True)


ana = on_command('analytics', required_superuser=True)


@ana.handle()
async def _(msg: MessageSession):
    if Config('enable_analytics'):
        first_record = BotDBUtil.Analytics.get_first()
        get_counts = BotDBUtil.Analytics.get_count()
        await msg.finish(f'机器人已执行命令次数（自{str(first_record.timestamp)}开始统计）：{get_counts}')
    else:
        await msg.finish('机器人未开启命令统计功能。')


@ana.handle('days [<name>]')
async def _(msg: MessageSession):
    if Config('enable_analytics'):
        first_record = BotDBUtil.Analytics.get_first()
        module_ = None
        if msg.parsed_msg['<name>']:
            module_ = msg.parsed_msg['<name>']
        data_ = {}
        for d in range(30):
            new = datetime.now().replace(hour=0, minute=0, second=0) + timedelta(days=1) - timedelta(days=30 - d - 1)
            old = datetime.now().replace(hour=0, minute=0, second=0) + timedelta(days=1) - timedelta(days=30 - d)
            get_ = BotDBUtil.Analytics.get_count_by_times(new, old, module_)
            data_[old.day] = get_
        data_x = []
        data_y = []
        for x in data_:
            data_x.append(str(x))
            data_y.append(data_[x])
        print(data_y)
        plt.plot(data_x, data_y, "-o")
        plt.plot(data_x[-1], data_y[-1], "-ro")
        plt.xlabel('Days')
        plt.ylabel('Counts')
        plt.tick_params(axis='x', labelrotation=45, which='major', labelsize=10)

        plt.gca().yaxis.get_major_locator().set_params(integer=True)
        for xitem, yitem in np.nditer([data_x, data_y]):
            plt.annotate(yitem, (xitem, yitem), textcoords="offset points", xytext=(0, 10), ha="center")
        path = random_cache_path() + '.png'
        plt.savefig(path)
        plt.close()
        await msg.finish(
            [Plain(f'最近30天的{module_ if module_ is not None else ""}命令调用次数统计（自{str(first_record.timestamp)}开始统计）：'),
             Image(path)])


ae = on_command('abuse', alias=['ae'], developers=['Dianliang233'], required_superuser=True)


@ae.handle('check <user>')
async def _(msg: MessageSession):
    user = msg.parsed_msg['<user>']
    if not user.startswith(f'{msg.target.senderFrom}|'):
        await msg.finish(f'ID格式错误。')
    warns = BotDBUtil.SenderInfo(user).query.warns
    await msg.finish(f'{user} 已被警告 {warns} 次。')


@ae.handle('warn <user> [<count>]')
async def _(msg: MessageSession):
    count = int(msg.parsed_msg['<count>'] or 1)
    user = msg.parsed_msg['<user>']
    if not user.startswith(f'{msg.target.senderFrom}|'):
        await msg.finish(f'ID格式错误。')
    warn_count = await warn_user(user, count)
    await msg.finish(f'成功警告 {user} {count} 次。此用户已被警告 {warn_count} 次。')


@ae.handle('revoke <user> [<count>]')
async def _(msg: MessageSession):
    count = 0 - int(msg.parsed_msg['<count>'] or 1)
    user = msg.parsed_msg['<user>']
    if not user.startswith(f'{msg.target.senderFrom}|'):
        await msg.finish(f'ID格式错误。')
    warn_count = await warn_user(user, count)
    await msg.finish(f'成功移除警告 {user} 的 {abs(count)} 次警告。此用户已被警告 {warn_count} 次。')


@ae.handle('clear <user>')
async def _(msg: MessageSession):
    user = msg.parsed_msg['<user>']
    if not user.startswith(f'{msg.target.senderFrom}|'):
        await msg.finish(f'ID格式错误。')
    await pardon_user(user)
    await msg.finish(f'成功清除 {user} 的警告。')


@ae.handle('untempban <user>')
async def _(msg: MessageSession):
    user = msg.parsed_msg['<user>']
    if not user.startswith(f'{msg.target.senderFrom}|'):
        await msg.finish(f'ID格式错误。')
    await remove_temp_ban(user)
    await msg.finish(f'成功解除 {user} 的临时限制。')


@ae.handle('ban <user>')
async def _(msg: MessageSession):
    user = msg.parsed_msg['<user>']
    if not user.startswith(f'{msg.target.senderFrom}|'):
        await msg.finish(f'ID格式错误。')
    if BotDBUtil.SenderInfo(user).edit('isInBlockList', True):
        await msg.finish(f'成功成功封禁 {user}。')


@ae.handle('unban <user>')
async def _(msg: MessageSession):
    user = msg.parsed_msg['<user>']
    if not user.startswith(f'{msg.target.senderFrom}|'):
        await msg.finish(f'ID格式错误。')
    if BotDBUtil.SenderInfo(user).edit('isInBlockList', False):
        await msg.finish(f'成功解除 {user} 的封禁。')


"""
@on_command('set_modules', required_superuser=True, help_doc='set_modules <>')
async def set_modules(display_msg: dict):
    ...
"""

rst = on_command('restart', developers=['OasisAkari'], required_superuser=True)


def restart():
    sys.exit(233)


def write_version_cache(msg: MessageSession):
    update = os.path.abspath(PrivateAssets.path + '/cache_restart_author')
    write_version = open(update, 'w')
    write_version.write(json.dumps({'From': msg.target.targetFrom, 'ID': msg.target.targetId}))
    write_version.close()


restart_time = []


async def wait_for_restart(msg: MessageSession):
    get = ExecutionLockList.get()
    if datetime.now().timestamp() - restart_time[0] < 60:
        if len(get) != 0:
            await msg.sendMessage(f'有 {len(get)} 个命令正在执行中，将于执行完毕后重启。')
            await asyncio.sleep(10)
            return await wait_for_restart(msg)
        else:
            await msg.sendMessage('重启中...')
            get_wait_list = MessageTaskManager.get()
            for x in get_wait_list:
                for y in get_wait_list[x]:
                    if get_wait_list[x][y]['active']:
                        print(x, y)
                        await get_wait_list[x][y]['original_session'].sendMessage('由于机器人正在重启，您此次执行命令的后续操作已被强制取消。'
                                                                                  '请稍后重新执行命令，对此带来的不便，我们深感抱歉。')

    else:
        await msg.sendMessage('等待已超时，强制重启中...')


@rst.handle()
async def restart_bot(msg: MessageSession):
    await msg.sendMessage('你确定吗？')
    confirm = await msg.waitConfirm()
    if confirm:
        restart_time.append(datetime.now().timestamp())
        await wait_for_restart(msg)
        write_version_cache(msg)
        restart()


upd = on_command('update', developers=['OasisAkari'], required_superuser=True)


def pull_repo():
    return os.popen('git pull', 'r').read()[:-1]


@upd.handle()
async def update_bot(msg: MessageSession):
    await msg.sendMessage('你确定吗？')
    confirm = await msg.waitConfirm()
    if confirm:
        await msg.sendMessage(pull_repo())


upds = on_command('update&restart', developers=['OasisAkari'], required_superuser=True)


@upds.handle()
async def update_and_restart_bot(msg: MessageSession):
    await msg.sendMessage('你确定吗？')
    confirm = await msg.waitConfirm()
    if confirm:
        restart_time.append(datetime.now().timestamp())
        await wait_for_restart(msg)
        write_version_cache(msg)
        await msg.sendMessage(pull_repo())
        restart()


echo = on_command('echo', developers=['OasisAkari'], required_superuser=True)


@echo.handle('<display_msg>')
async def _(msg: MessageSession):
    await msg.finish(msg.parsed_msg['<display_msg>'])


say = on_command('say', developers=['OasisAkari'], required_superuser=True)


@say.handle('<display_msg>')
async def _(msg: MessageSession):
    await msg.finish(msg.parsed_msg['<display_msg>'], quote=False)


tog = on_command('toggle', developers=['OasisAkari'], base=True, required_admin=True)


@tog.handle('typing {切换是否展示输入提示}')
async def _(msg: MessageSession):
    target = BotDBUtil.SenderInfo(msg.target.senderId)
    state = target.query.disable_typing
    if not state:
        target.edit('disable_typing', True)
        await msg.finish('成功关闭输入提示。')
    else:
        target.edit('disable_typing', False)
        await msg.finish('成功打开输入提示。')


@tog.handle('check {切换是否展示命令错字检查提示}')
async def _(msg: MessageSession):
    options = BotDBUtil.Options(msg)
    state = options.get('typo_check')
    if state is None:
        state = False
    else:
        state = not state
    BotDBUtil.Options(msg).edit('typo_check', state)
    await msg.finish(f'成功{"打开" if state else "关闭"}错字检查提示。')


mute = on_command('mute', developers=['Dianliang233'], base=True, required_admin=True,
                  desc='使机器人停止发言。')


@mute.handle()
async def _(msg: MessageSession):
    if BotDBUtil.Muting(msg).check():
        BotDBUtil.Muting(msg).remove()
        await msg.finish('成功取消禁言。')
    else:
        BotDBUtil.Muting(msg).add()
        await msg.finish('成功禁言。')


leave = on_command('leave', developers=['OasisAkari'], base=True, required_admin=True, available_for='QQ|Group',
                   desc='使机器人离开群聊。')


@leave.handle()
async def _(msg: MessageSession):
    confirm = await msg.waitConfirm('你确定吗？此操作不可逆。')
    if confirm:
        await msg.sendMessage('已执行。')
        await msg.call_api('set_group_leave', group_id=msg.session.target)
