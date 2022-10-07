import traceback

from core.builtins.message import MessageSession
from core.component import on_command
from core.elements import Command, Image, Plain
from core.exceptions import InvalidHelpDocTypeError
from core.loader import ModulesManager
from core.parser.command import CommandParser
from core.utils.image_table import ImageTable, image_table_render, web_render
from database import BotDBUtil

module = on_command('module',
                    base=True,
                    alias={'enable': 'module enable', 'disable': 'module disable'},
                    developers=['OasisAkari'],
                    required_admin=True
                    )


@module.handle(['enable <module>... {开启一个/多个模块}',
                'enable all {开启所有模块}',
                'disable <module>... {关闭一个/多个模块}',
                'disable all {关闭所有模块。}',
                'list {查看所有可用模块}'], exclude_from=['QQ|Guild'])
async def _(msg: MessageSession):
    if msg.parsed_msg.get('list', False):
        await modules_help(msg)
    await config_modules(msg)


@module.handle(['enable [-g] <module>... {开启一个/多个模块}',
                'enable all [-g] {开启所有模块}',
                'disable [-g] <module>... {关闭一个/多个模块}',
                'disable all [-g] {关闭所有模块。}',
                'list {查看所有可用模块}'], options_desc={'-g': '对频道进行全局操作'},
               available_for=['QQ|Guild'])
async def _(msg: MessageSession):
    if msg.parsed_msg.get('list', False):
        await modules_help(msg)
    await config_modules(msg)


async def config_modules(msg: MessageSession):
    alias = ModulesManager.return_modules_alias_map()
    modules_ = ModulesManager.return_modules_list_as_dict(targetFrom=msg.target.targetFrom)
    enabled_modules_list = BotDBUtil.TargetInfo(msg).enabled_modules
    wait_config = [msg.parsed_msg.get('<module>')] + msg.parsed_msg.get('...', [])
    wait_config_list = []
    for module_ in wait_config:
        if module_ not in wait_config_list:
            if module_ in alias:
                wait_config_list.append(alias[module_])
            else:
                wait_config_list.append(module_)
    msglist = []
    recommend_modules_list = []
    recommend_modules_help_doc_list = []
    if msg.parsed_msg.get('enable', False):
        enable_list = []
        if msg.parsed_msg.get('all', False):
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
                query = BotDBUtil.TargetInfo(f'{msg.target.targetFrom}|{x}')
                query.enable(enable_list)
            for x in enable_list:
                msglist.append(f'成功：为所有文字频道打开“{x}”模块')
        else:
            if msg.data.enable(enable_list):
                for x in enable_list:
                    if x in enabled_modules_list:
                        msglist.append(f'失败：“{x}”模块已经开启')
                    else:
                        msglist.append(f'成功：打开模块“{x}”')
        if recommend_modules_list:
            for m in recommend_modules_list:
                try:
                    recommend_modules_help_doc_list.append(f'模块{m}的帮助信息：')

                    if modules_[m].desc is not None:
                        recommend_modules_help_doc_list.append(modules_[m].desc)
                    if isinstance(modules_[m], Command):
                        hdoc = CommandParser(modules_[m], msg=msg, bind_prefix=modules_[m].bind_prefix,
                                             command_prefixes=msg.prefixes).return_formatted_help_doc()
                        recommend_modules_help_doc_list.append(hdoc)
                except InvalidHelpDocTypeError:
                    pass
    elif msg.parsed_msg.get('disable', False):
        disable_list = []
        if msg.parsed_msg.get('all', False):
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
                query = BotDBUtil.TargetInfo(f'{msg.target.targetFrom}|{x}')
                query.disable(disable_list)
            for x in disable_list:
                msglist.append(f'成功：为所有文字频道关闭“{x}”模块')
        else:
            if msg.data.disable(disable_list):
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
            if msg.data.enable(recommend_modules_list):
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
            if isinstance(module_, Command):
                help_ = CommandParser(module_list[help_name], msg=msg, bind_prefix=module_list[help_name].bind_prefix,
                                      command_prefixes=msg.prefixes)
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


@hlp.handle('{查看帮助列表}')
async def _(msg: MessageSession):
    module_list = ModulesManager.return_modules_list_as_dict(targetFrom=msg.target.targetFrom)
    target_enabled_list = msg.enabled_modules
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
                doc_ = []
                if isinstance(module_, Command):
                    help_ = CommandParser(module_, msg=msg, bind_prefix=module_.bind_prefix,
                                          command_prefixes=msg.prefixes)

                    if module_.desc is not None:
                        doc_.append(module_.desc)
                    if help_.args is not None:
                        doc_.append(help_.return_formatted_help_doc())
                else:
                    if module_.desc is not None:
                        doc_.append(module_.desc)
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
                                      Plain(
                                          f'此处展示的帮助文档仅展示已开启的模块，若需要查看全部模块的帮助文档，请使用{msg.prefixes[0]}module list命令。'
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
                doc_ = []
                if isinstance(module_, Command):
                    help_ = CommandParser(module_, bind_prefix=module_.bind_prefix, command_prefixes=msg.prefixes)
                    if module_.desc is not None:
                        doc_.append(module_.desc)
                    if help_.args is not None:
                        doc_.append(help_.return_formatted_help_doc())
                else:
                    if module_.desc is not None:
                        doc_.append(module_.desc)
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
