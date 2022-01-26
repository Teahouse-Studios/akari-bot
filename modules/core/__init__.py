import os
import sys
import time
import traceback

import psutil
import ujson as json

from core.component import on_command
from core.elements import MessageSession, Command, PrivateAssets, Image, Plain
from core.loader import ModulesManager
from core.parser.command import CommandParser, InvalidHelpDocTypeError
from core.parser.message import remove_temp_ban
from core.tos import pardon_user, warn_user
from core.utils.image_table import ImageTable, image_table_render, web_render
from database import BotDBUtil

module = on_command('module',
                    base=True,
                    alias={'enable': 'module enable', 'disable': 'module disable'},
                    developers=['OasisAkari'],
                    required_admin=True
                    )


@module.handle(['enable (<module>...|all) {开启一个/多个或所有模块}',
                'disable (<module>...|all) {关闭一个/多个或所有模块}'], exclude_from=['QQ|Guild'])
async def _(msg: MessageSession):
    await config_modules(msg)


@module.handle(['enable (<module>...|all) [-g] {开启一个/多个或所有模块}',
                'disable (<module>...|all) [-g] {关闭一个/多个或所有模块\n [-g] - 为文字频道内全局操作}'],
               available_for=['QQ|Guild'])
async def _(msg: MessageSession):
    await config_modules(msg)


async def config_modules(msg: MessageSession):
    alias = ModulesManager.return_modules_alias_map()
    modules_ = ModulesManager.return_modules_list_as_dict(targetFrom=msg.target.targetFrom)
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
                    msglist.append(f'成功：打开模块“{x}”')
        if recommend_modules_list:
            for m in recommend_modules_list:
                if m not in enable_list:
                    try:
                        hdoc = CommandParser(modules_[m], msg=msg).return_formatted_help_doc()
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
                    msglist.append(f'成功：关闭模块“{x}”')
    if msglist is not None:
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
                await msg.sendMessage('\n'.join(msglist))


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
            help_ = CommandParser(module_list[help_name], msg=msg)
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
            await msg.sendMessage(doc + devs_msg)
        else:
            await msg.sendMessage('此模块可能不存在，请检查输入。')


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
                help_ = CommandParser(module_, msg=msg)
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
                    await msg.sendMessage([Image(render),
                                           Plain('此处展示的帮助文档仅展示已开启的模块，若需要查看全部模块的帮助文档，请使用~modules命令。'
                                                 '\n你也可以通过查阅文档获取帮助：\nhttps://bot.teahou.se/wiki/')])
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
            '使用~help <对应模块名>查看详细信息。\n使用~modules查看所有的可用模块。\n你也可以通过查阅文档获取帮助：\nhttps://bot.teahou.se/wiki/')
        if msg.Feature.delete:
            help_msg.append('[本消息将在一分钟后撤回]')
        send = await msg.sendMessage('\n'.join(help_msg))
        await msg.sleep(60)
        await send.delete()


modules = on_command('modules',
                     base=True,
                     desc='查看所有可用模块',
                     developers=['OasisAkari']
                     )


@modules.handle()
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
                help_ = CommandParser(module_)
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
                    await msg.sendMessage([Image(render)])
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
            '使用~help <模块名>查看详细信息。\n你也可以通过查阅文档获取帮助：\nhttps://bot.teahou.se/wiki/')
        if msg.Feature.delete:
            help_msg.append('[本消息将在一分钟后撤回]')
        send = await msg.sendMessage('\n'.join(help_msg))
        await msg.sleep(60)
        await send.delete()


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
    await msg.sendMessage(msgs, msgs)
    open_version.close()


ping = on_command('ping',
                  base=True,
                  desc='获取机器人状态',
                  developers=['OasisAkari']
                  )


@ping.handle()
async def _(msg: MessageSession):
    checkpermisson = msg.checkSuperUser()
    result = "Pong!"
    if checkpermisson:
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
                   + f"\n当前CPU使用率：{Cpu_usage}{BFH}"
                   + f"\n物理内存：{RAM}M 使用率：{RAM_percent}{BFH}"
                   + f"\nSwap内存：{Swap}M 使用率：{Swap_percent}{BFH}"
                   + f"\n磁盘容量：{Disk}G/{DiskTotal}G"
                   # + f"\n已加入QQ群聊：{GroupList}"
                   # + f" | 已添加QQ好友：{FriendList}" """
                   )
    await msg.sendMessage(result)


admin = on_command('admin',
                   base=True,
                   required_admin=True,
                   developers=['OasisAkari']
                   )


@admin.handle(['add <UserID> {设置成员为机器人管理员}', 'del <UserID> {取消成员的机器人管理员}'])
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


su = on_command('superuser', alias=['su'], developers=['OasisAkari', 'Dianliang233'], required_superuser=True)


@su.handle('add <user>')
async def add_su(message: MessageSession):
    user = message.parsed_msg['<user>']
    print(message.parsed_msg)
    if user:
        if BotDBUtil.SenderInfo(user).edit('isSuperUser', True):
            await message.sendMessage('操作成功：已将' + user + '设置为超级用户。')


@su.handle('del <user>')
async def del_su(message: MessageSession):
    user = message.parsed_msg['<user>']
    if user:
        if BotDBUtil.SenderInfo(user).edit('isSuperUser', False):
            await message.sendMessage('操作成功：已将' + user + '移出超级用户。')


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
    await msg.sendMessage(f'你的 ID 是：{msg.target.senderId}\n本对话的 ID 是：{msg.target.targetId}' + rights,
                          disable_secret_check=True)


ae = on_command('abuse', alias=['ae'], developers=['Dianliang233'], required_superuser=True)


@ae.handle('check <user>')
async def _(msg: MessageSession):
    user = msg.parsed_msg['<user>']
    warns = BotDBUtil.SenderInfo(user).query.warns
    await msg.sendMessage(f'{user} 已被警告 {warns} 次。')


@ae.handle('warn <user> [<count>]')
async def _(msg: MessageSession):
    count = int(msg.parsed_msg['<count>'] or 1)
    user = msg.parsed_msg['<user>']
    warn_count = await warn_user(user, count)
    await msg.sendMessage(f'成功警告 {user} {count} 次。此用户已被警告 {warn_count} 次。')


@ae.handle('revoke <user> [<count>]')
async def _(msg: MessageSession):
    count = 0 - int(msg.parsed_msg['<count>'] or -1)
    user = msg.parsed_msg['<user>']
    warn_count = await warn_user(user, count)
    await msg.sendMessage(f'成功移除警告 {user} 的 {count} 次警告。此用户已被警告 {warn_count} 次。')


@ae.handle('clear <user>')
async def _(msg: MessageSession):
    user = msg.parsed_msg['<user>']
    await pardon_user(user)
    await msg.sendMessage(f'成功清除 {user} 的警告。')


@ae.handle('untempban <user>')
async def _(msg: MessageSession):
    user = msg.parsed_msg['<user>']
    await remove_temp_ban(user)
    await msg.sendMessage(f'成功解除 {user} 的临时封禁。')


@ae.handle('ban <user>')
async def _(msg: MessageSession):
    user = msg.parsed_msg['<user>']
    if BotDBUtil.SenderInfo(user).edit('isInBlockList', True):
        await msg.sendMessage(f'成功封禁 {user}。')


@ae.handle('unban <user>')
async def _(msg: MessageSession):
    user = msg.parsed_msg['<user>']
    if BotDBUtil.SenderInfo(user).edit('isInBlockList', False):
        await msg.sendMessage(f'成功解除 {user} 的封禁。')


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


@rst.handle()
async def restart_bot(msg: MessageSession):
    await msg.sendMessage('你确定吗？')
    confirm = await msg.waitConfirm()
    if confirm:
        write_version_cache(msg)
        await msg.sendMessage('已执行。')
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
        write_version_cache(msg)
        await msg.sendMessage(pull_repo())
        restart()


echo = on_command('echo', developers=['OasisAkari'], required_superuser=True)


@echo.handle('<display_msg>')
async def _(msg: MessageSession):
    await msg.sendMessage(msg.parsed_msg['<display_msg>'])


say = on_command('say', developers=['OasisAkari'], required_superuser=True)


@say.handle('<display_msg>')
async def _(msg: MessageSession):
    await msg.sendMessage(msg.parsed_msg['<display_msg>'], quote=False)


tog = on_command('toggle', developers=['OasisAkari'], base=True)


@tog.handle('typing {切换是否展示输入提示}')
async def _(msg: MessageSession):
    target = BotDBUtil.SenderInfo(msg.target.senderId)
    state = target.query.disable_typing
    if not state:
        target.edit('disable_typing', True)
        await msg.sendMessage('成功关闭输入提示。')
    else:
        target.edit('disable_typing', False)
        await msg.sendMessage('成功打开输入提示。')


mute = on_command('mute', developers=['Dianliang233'], base=True, required_admin=True)


@mute.handle()
async def _(msg: MessageSession):
    if BotDBUtil.Muting(msg).check():
        BotDBUtil.Muting(msg).remove()
        await msg.sendMessage('成功取消禁言。')
    else:
        BotDBUtil.Muting(msg).add()
        await msg.sendMessage('成功禁言。')
