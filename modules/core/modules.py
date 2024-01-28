import re
import traceback

from config import Config, CFG
from core.builtins import Image, Plain, Bot
from core.component import module
from core.exceptions import InvalidHelpDocTypeError
from core.loader import ModulesManager, current_unloaded_modules, err_modules
from core.parser.command import CommandParser
from core.utils.i18n import load_locale_file
from core.utils.image_table import ImageTable, image_table_render
from database import BotDBUtil

m = module('module',
           base=True,
           alias={'enable': 'module enable',
                  'disable': 'module disable',
                  'load': 'module load',
                  'reload': 'module reload',
                  'unload': 'module unload'},
           required_admin=True
           )


@m.command(['enable <module>... {{core.help.module.enable}}',
            'enable all {{core.help.module.enable_all}}',
            'disable <module>... {{core.help.module.disable}}',
            'disable all {{core.help.module.disable_all}}',
            'reload <module> ...',
            'load <module> ...',
            'unload <module> ...',
            'list {{core.help.module.list}}',
            'list legacy {{core.help.module.list.legacy}}'], exclude_from=['QQ|Guild'])
async def _(msg: Bot.MessageSession):
    if msg.parsed_msg.get('list', False):
        legacy = False
        if msg.parsed_msg.get('legacy', False):
            legacy = True
        await modules_help(msg, legacy)
    await config_modules(msg)


@m.command(['enable <module> ... {{core.help.module.enable}}',
            'enable all {{core.help.module.enable_all}}',
            'disable <module> ... {{core.help.module.disable}}',
            'disable all {{core.help.module.disable_all}}',
            'reload <module> ...',
            'load <module> ...',
            'unload <module> ...',
            'list {{core.help.module.list}}',
            'list legacy {{core.help.module.list.legacy}}'],
           options_desc={'-g': '{core.help.option.module.g}'},
           available_for=['QQ|Guild'])
async def _(msg: Bot.MessageSession):
    if msg.parsed_msg.get('list', False):
        legacy = False
        if msg.parsed_msg.get('legacy', False):
            legacy = True
        await modules_help(msg, legacy)
    await config_modules(msg)


async def config_modules(msg: Bot.MessageSession):
    alias = ModulesManager.modules_aliases
    modules_ = ModulesManager.return_modules_list(
        target_from=msg.target.target_from)
    enabled_modules_list = BotDBUtil.TargetInfo(msg).enabled_modules
    wait_config = [msg.parsed_msg.get(
        '<module>')] + msg.parsed_msg.get('...', [])
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
                if modules_[function].base or modules_[function].required_superuser:
                    continue
                enable_list.append(function)
        else:
            for module_ in wait_config_list:
                if module_ not in modules_:
                    msglist.append(msg.locale.t("core.message.module.enable.not_found", module=module_))
                else:
                    if modules_[module_].required_superuser and not msg.check_super_user():
                        msglist.append(msg.locale.t("cparser.superuser.permission.denied"))
                    elif modules_[module_].base:
                        msglist.append(msg.locale.t("core.message.module.enable.base", module=module_))
                    else:
                        enable_list.append(module_)
                        recommend = modules_[module_].recommend_modules
                        if recommend:
                            for r in recommend:
                                if r not in enable_list and r not in enabled_modules_list:
                                    recommend_modules_list.append(r)
        if '-g' in msg.parsed_msg and msg.parsed_msg['-g']:
            get_all_channel = await msg.get_text_channel_list()
            for x in get_all_channel:
                query = BotDBUtil.TargetInfo(f'{msg.target.target_from}|{x}')
                query.enable(enable_list)
            for x in enable_list:
                msglist.append(msg.locale.t("core.message.module.enable.qq_channel_global.success", module=x))
        else:
            if msg.data.enable(enable_list):
                for x in enable_list:
                    if x in enabled_modules_list:
                        msglist.append(msg.locale.t("core.message.module.enable.already", module=x))
                    else:
                        msglist.append(msg.locale.t("core.message.module.enable.success", module=x))
                        support_lang = modules_[x].support_languages
                        if support_lang:
                            if msg.locale.locale not in support_lang:
                                msglist.append(msg.locale.t("core.message.module.unsupported_language",
                                                            module=x))
        if recommend_modules_list:
            for m in recommend_modules_list:
                try:
                    recommend_modules_help_doc_list.append(msg.locale.t("core.message.module.recommends.help", module=m
                                                                        ))

                    if modules_[m].desc:
                        recommend_modules_help_doc_list.append(msg.locale.tl_str(modules_[m].desc))
                    hdoc = CommandParser(modules_[m], msg=msg, bind_prefix=modules_[m].bind_prefix,
                                         command_prefixes=msg.prefixes).return_formatted_help_doc()
                    if not hdoc:
                        hdoc = msg.locale.t('core.help.none')
                    recommend_modules_help_doc_list.append(hdoc)
                except InvalidHelpDocTypeError:
                    pass
    elif msg.parsed_msg.get('disable', False):
        disable_list = []
        if msg.parsed_msg.get('all', False):
            for function in modules_:
                if function[0] == '_':
                    continue
                if modules_[function].base or modules_[function].required_superuser:
                    continue
                disable_list.append(function)
        else:
            for module_ in wait_config_list:
                if module_ not in modules_:
                    msglist.append(msg.locale.t("core.message.module.disable.not_found", module=module_))
                else:
                    if modules_[module_].required_superuser and not msg.check_super_user():
                        msglist.append(msg.locale.t("parser.superuser.permission.denied"))
                    elif modules_[module_].base:
                        msglist.append(msg.locale.t("core.message.module.disable.base", module=module_))
                    else:
                        disable_list.append(module_)
        if '-g' in msg.parsed_msg and msg.parsed_msg['-g']:
            get_all_channel = await msg.get_text_channel_list()
            for x in get_all_channel:
                query = BotDBUtil.TargetInfo(f'{msg.target.target_from}|{x}')
                query.disable(disable_list)
            for x in disable_list:
                msglist.append(msg.locale.t("core.message.module.disable.qqchannel_global.success", module=x))
        else:
            if msg.data.disable(disable_list):
                for x in disable_list:
                    if x not in enabled_modules_list:
                        msglist.append(msg.locale.t("core.message.module.disable.already", module=x))
                    else:
                        msglist.append(msg.locale.t("core.message.module.disable.success", module=x))
    elif msg.parsed_msg.get('reload', False):
        if msg.check_super_user():
            def module_reload(module, extra_modules, base_module=False):
                reload_count = ModulesManager.reload_module(module)
                if base_module and reload_count >= 1:
                    return msg.locale.t("core.message.module.reload.base.success")
                elif reload_count > 1:
                    return msg.locale.t('core.message.module.reload.success', module=module) + \
                        ('\n' if len(extra_modules) != 0 else '') + \
                        '\n'.join(extra_modules) + \
                        '\n' + msg.locale.t('core.message.module.reload.with', reloadCnt=reload_count - 1)
                elif reload_count == 1:
                    return msg.locale.t('core.message.module.reload.success', module=module) + \
                        ('\n' if len(extra_modules) != 0 else '') + \
                        '\n'.join(extra_modules) + \
                        '\n' + msg.locale.t('core.message.module.reload.no_more')
                else:
                    return msg.locale.t("core.message.module.reload.failed")

            for module_ in wait_config_list:
                base_module = False
                if '-f' in msg.parsed_msg and msg.parsed_msg['-f']:
                    msglist.append(module_reload(module_, []))
                elif module_ not in modules_:
                    msglist.append(msg.locale.t("core.message.module.reload.not_found", module=module_))
                else:
                    extra_reload_modules = ModulesManager.search_related_module(module_, False)
                    if modules_[module_].base:
                        if Config('debug'):
                            confirm = await msg.wait_confirm(msg.locale.t("core.message.module.reload.base.confirm"),
                                                                          append_instruction=False)
                            if confirm:
                                base_module = True
                            else:
                                await msg.finish()
                        else:
                            await msg.finish(msg.locale.t("core.message.module.reload.base.failed", module=module_))

                    elif len(extra_reload_modules):
                        confirm = await msg.wait_confirm(msg.locale.t("core.message.module.reload.confirm",
                                                                      modules='\n'.join(extra_reload_modules)), append_instruction=False)
                        if not confirm:
                            await msg.finish()
                    unloaded_list = CFG.get('unloaded_modules')
                    if unloaded_list and module_ in unloaded_list:
                        unloaded_list.remove(module_)
                        CFG.write('unloaded_modules', unloaded_list)
                    msglist.append(module_reload(module_, extra_reload_modules, base_module))

            locale_err = load_locale_file()
            if len(locale_err) != 0:
                msglist.append(msg.locale.t("core.message.locale.reload.failed", detail='\n'.join(locale_err)))
        else:
            msglist.append(msg.locale.t("parser.superuser.permission.denied"))
    elif msg.parsed_msg.get('load', False):
        if msg.check_super_user():

            for module_ in wait_config_list:
                if module_ not in current_unloaded_modules:
                    msglist.append(msg.locale.t("core.message.module.load.not_found"))
                    continue
                if ModulesManager.load_module(module_):
                    msglist.append(msg.locale.t("core.message.module.load.success", module=module_))
                    unloaded_list = CFG.get('unloaded_modules')
                    if unloaded_list and module_ in unloaded_list:
                        unloaded_list.remove(module_)
                        CFG.write('unloaded_modules', unloaded_list)
                else:
                    msglist.append(msg.locale.t("core.message.module.load.failed"))

        else:
            msglist.append(msg.locale.t("parser.superuser.permission.denied"))

    elif msg.parsed_msg.get('unload', False):
        if msg.check_super_user():

            for module_ in wait_config_list:
                if module_ not in modules_:
                    if module_ in err_modules:
                        if await msg.wait_confirm(msg.locale.t("core.message.module.unload.unavailable.confirm"), append_instruction=False):
                            unloaded_list = CFG.get('unloaded_modules')
                            if not unloaded_list:
                                unloaded_list = []
                            if module_ not in unloaded_list:
                                unloaded_list.append(module_)
                                CFG.write('unloaded_modules', unloaded_list)
                            msglist.append(msg.locale.t("core.message.module.unload.success", module=module_))
                            err_modules.remove(module_)
                            current_unloaded_modules.append(module_)
                        else:
                            await msg.finish()
                    else:
                        msglist.append(msg.locale.t("core.message.module.unload.not_found"))
                    continue
                if modules_[module_].base:
                    msglist.append(msg.locale.t("core.message.module.unload.base", module=module_))
                    continue
                if await msg.wait_confirm(msg.locale.t("core.message.module.unload.confirm"), append_instruction=False):
                    if ModulesManager.unload_module(module_):
                        msglist.append(msg.locale.t("core.message.module.unload.success", module=module_))
                        unloaded_list = CFG.get('unloaded_modules')
                        if not unloaded_list:
                            unloaded_list = []
                        unloaded_list.append(module_)
                        CFG.write('unloaded_modules', unloaded_list)
                else:
                    await msg.finish()

        else:
            msglist.append(msg.locale.t("parser.superuser.permission.denied"))

    if msglist:
        if not recommend_modules_help_doc_list:
            await msg.finish('\n'.join(msglist))
        else:
            await msg.send_message('\n'.join(msglist))
    if recommend_modules_help_doc_list and ('-g' not in msg.parsed_msg or not msg.parsed_msg['-g']):
        confirm = await msg.wait_confirm(msg.locale.t("core.message.module.recommends",
                                                      modules='\n'.join(recommend_modules_list) + '\n\n' +
                                                           '\n'.join(recommend_modules_help_doc_list)))
        if confirm:
            if msg.data.enable(recommend_modules_list):
                msglist = []
                for x in recommend_modules_list:
                    msglist.append(msg.locale.t("core.message.module.enable.success", module=x))
                await msg.finish('\n'.join(msglist))
        else:
            await msg.finish()
    else:
        return


hlp = module('help', base=True)


@hlp.command('<module> {{core.help.help.detail}}')
async def bot_help(msg: Bot.MessageSession):
    module_list = ModulesManager.return_modules_list(
        target_from=msg.target.target_from)
    alias = ModulesManager.modules_aliases
    if msg.parsed_msg:
        msgs = []
        help_name = msg.parsed_msg['<module>']
        if help_name in alias:
            help_name = alias[help_name]
        if help_name in module_list:
            module_ = module_list[help_name]
            if module_.desc:
                desc = module_.desc
                if locale_str := re.match(r'\{(.*)}', desc):
                    if locale_str:
                        desc = msg.locale.t(locale_str.group(1))
                msgs.append(desc)
            help_ = CommandParser(module_list[help_name], msg=msg, bind_prefix=module_list[help_name].bind_prefix,
                                  command_prefixes=msg.prefixes)
            if help_.args:
                msgs.append(help_.return_formatted_help_doc())

            doc = '\n'.join(msgs)
            if module_.regex_list.set:
                doc += '\n' + msg.locale.t("core.message.help.support_regex")
                for regex in module_.regex_list.set:
                    pattern = None
                    if isinstance(regex.pattern, str):
                        pattern = regex.pattern
                    elif isinstance(regex.pattern, re.Pattern):
                        pattern = regex.pattern.pattern
                    if pattern:
                        desc = regex.desc
                        if desc:
                            doc += f'\n{pattern} ' + msg.locale.t("core.message.help.regex.detail",
                                                                  msg=msg.locale.tl_str(desc))
                        else:
                            doc += f'\n{pattern} ' + msg.locale.t("core.message.help.regex.no_information")
            module_alias = module_.alias
            malias = []
            if module_alias:
                for a in module_alias:
                    malias.append(f'{a} -> {module_alias[a]}')
            if module_.developers:
                devs = msg.locale.t('message.delimiter').join(module_.developers)
                devs_msg = '\n' + msg.locale.t("core.message.help.author.type1") + devs
            else:
                devs_msg = ''
            if Config('help_url'):
                wiki_msg = '\n' + msg.locale.t("core.message.help.helpdoc.address",
                                           url=Config('help_url')) + '/' + help_name
            else:
                wiki_msg = ''
            if len(doc) > 500 and msg.Feature.image:
                try:
                    tables = [ImageTable([[doc, '\n'.join(malias), devs]],
                                         [msg.locale.t("core.message.help.table.header.help"),
                                          msg.locale.t("core.message.help.table.header.alias"),
                                          msg.locale.t("core.message.help.author.type2")])]
                    render = await image_table_render(tables)
                    if render:
                        await msg.finish([Image(render),
                                          Plain(wiki_msg)])
                except Exception:
                    traceback.print_exc()
            if malias:
                doc += f'\n{msg.locale.t("core.help.alias")}\n' + '\n'.join(malias)
            doc_msg = (doc + devs_msg + wiki_msg).lstrip()
            if doc_msg != '':
                await msg.finish(doc_msg)
            else:
                await msg.finish(msg.locale.t("core.help.none"))
        else:
            await msg.finish(msg.locale.t("core.message.help.not_found"))


@hlp.command(['{{core.help.help}}',
              'legacy {{core.help.help.legacy}}'])
async def _(msg: Bot.MessageSession):
    module_list = ModulesManager.return_modules_list(
        target_from=msg.target.target_from)
    target_enabled_list = msg.enabled_modules
    legacy_help = True
    if not msg.parsed_msg and msg.Feature.image:
        try:
            tables = []
            essential = []
            m = []
            for x in module_list:
                module_ = module_list[x]
                appends = [module_.bind_prefix]
                doc_ = []
                help_ = CommandParser(module_, msg=msg, bind_prefix=module_.bind_prefix,
                                      command_prefixes=msg.prefixes)

                if module_.desc:
                    doc_.append(msg.locale.tl_str(module_.desc))
                if help_.args:
                    doc_.append(help_.return_formatted_help_doc())
                doc = '\n'.join(doc_)
                if module_.regex_list.set:
                    doc += '\n' + msg.locale.t("core.message.help.support_regex")
                    for regex in module_.regex_list.set:
                        pattern = None
                        if isinstance(regex.pattern, str):
                            pattern = regex.pattern
                        elif isinstance(regex.pattern, re.Pattern):
                            pattern = regex.pattern.pattern
                        if pattern:
                            desc = regex.desc
                            if desc:
                                doc += f'\n{pattern} ' + msg.locale.t("core.message.help.regex.detail",
                                                                      msg=msg.locale.tl_str(desc))
                            else:
                                doc += f'\n{pattern} ' + msg.locale.t("core.message.help.regex.no_information")
                appends.append(doc)
                module_alias = module_.alias
                malias = []
                if module_alias:
                    for a in module_alias:
                        malias.append(f'{a} -> {module_alias[a]}')
                appends.append('\n'.join(malias) if malias else '')
                if module_.developers:
                    appends.append(msg.locale.t('message.delimiter').join(module_.developers))
                if module_.base and not (module_.required_superuser or module_.required_base_superuser):
                    essential.append(appends)
                if x in target_enabled_list and not (module_.required_superuser or module_.required_base_superuser):
                    m.append(appends)
            if essential:
                tables.append(ImageTable(
                    essential, [msg.locale.t("core.message.help.table.header.base"),
                                msg.locale.t("core.message.help.table.header.help"),
                                msg.locale.t("core.message.help.table.header.alias"),
                                msg.locale.t("core.message.help.author.type2")]))
            if m:
                tables.append(ImageTable(m, [msg.locale.t("core.message.help.table.header.external"),
                                             msg.locale.t("core.message.help.table.header.help"),
                                             msg.locale.t("core.message.help.table.header.alias"),
                                             msg.locale.t("core.message.help.author.type2")]))
            if tables:
                render = await image_table_render(tables)
                if render:
                    legacy_help = False
                    help_msg_list = [Image(render), Plain(msg.locale.t("core.message.help.more_information",
                                                         prefix=msg.prefixes[0]))]
                    if Config('help_url'):
                        help_msg_list.append(Plain(msg.locale.t("core.message.help.more_information.document",
                                                         url=Config('help_url'))))
                    if Config('donate_url'):
                        help_msg_list.append(Plain(msg.locale.t("core.message.help.more_information.donate",
                                                         url=Config('donate_url'))))
                    await msg.finish(help_msg_list)
        except Exception:
            traceback.print_exc()
    if legacy_help:
        help_msg = [msg.locale.t("core.message.help.legacy.base")]
        essential = []
        for x in module_list:
            if module_list[x].base and not (
                    module_list[x].required_superuser or module_list[x].required_base_superuser):
                essential.append(module_list[x].bind_prefix)
        help_msg.append(' | '.join(essential))
        help_msg.append(msg.locale.t("core.message.help.legacy.external"))
        module_ = []
        for x in module_list:
            if x in target_enabled_list and not (
                    module_list[x].required_superuser or module_list[x].required_base_superuser):
                module_.append(x)
        help_msg.append(' | '.join(module_))
        help_msg.append(
            msg.locale.t(
                "core.message.help.legacy.more_information",
                prefix=msg.prefixes[0]))
        if Config('help_url'):
            help_msg.append(
                msg.locale.t(
                    "core.message.help.more_information.document",
                    url=Config('help_url')))
        if Config('donate_url'):
            help_msg.append(
                msg.locale.t(
                    "core.message.help.more_information.donate",
                    url=Config('donate_url')))
        await msg.finish('\n'.join(help_msg))


async def modules_help(msg: Bot.MessageSession, legacy):
    module_list = ModulesManager.return_modules_list(
        target_from=msg.target.target_from)
    legacy_help = True
    if msg.Feature.image and not legacy:
        try:
            tables = []
            m = []
            for x in module_list:
                module_ = module_list[x]
                if x[0] == '_':
                    continue
                if module_.base or module_.required_superuser or module_.required_base_superuser:
                    continue
                appends = [module_.bind_prefix]
                doc_ = []
                help_ = CommandParser(
                    module_, bind_prefix=module_.bind_prefix, command_prefixes=msg.prefixes, msg=msg)
                if module_.desc:
                    doc_.append(msg.locale.tl_str(module_.desc))
                if help_.args:
                    doc_.append(help_.return_formatted_help_doc())
                doc = '\n'.join(doc_)
                if module_.regex_list.set:
                    doc += '\n' + msg.locale.t("core.message.help.support_regex")
                    for regex in module_.regex_list.set:
                        pattern = None
                        if isinstance(regex.pattern, str):
                            pattern = regex.pattern
                        elif isinstance(regex.pattern, re.Pattern):
                            pattern = regex.pattern.pattern
                        if pattern:
                            desc = regex.desc
                            if desc:
                                doc += f'\n{pattern} ' + msg.locale.t("core.message.help.regex.detail",
                                                                      msg=msg.locale.tl_str(desc))
                            else:
                                doc += f'\n{pattern} ' + msg.locale.t("core.message.help.regex.no_information")
                appends.append(doc)
                module_alias = module_.alias
                malias = []
                if module_alias:
                    for a in module_alias:
                        malias.append(f'{a} -> {module_alias[a]}')
                appends.append('\n'.join(malias) if malias else '')
                if module_.developers:
                    appends.append(msg.locale.t('message.delimiter').join(module_.developers))
                m.append(appends)
            if m:
                tables.append(ImageTable(m, [msg.locale.t("core.message.help.table.header.external"),
                                             msg.locale.t("core.message.help.table.header.help"),
                                             msg.locale.t("core.message.help.table.header.alias"),
                                             msg.locale.t("core.message.help.author.type2")]))
            if tables:
                render = await image_table_render(tables)
                if render:
                    legacy_help = False
                    await msg.finish([Image(render)])
        except Exception:
            traceback.print_exc()
    if legacy_help:
        help_msg = [msg.locale.t("core.message.help.legacy.availables")]
        module_ = []
        for x in module_list:
            if x[0] == '_':
                continue
            if module_list[x].base or module_list[x].required_superuser or module_list[x].required_base_superuser:
                continue
            module_.append(module_list[x].bind_prefix)
        help_msg.append(' | '.join(module_))
        help_msg.append(
            msg.locale.t(
                "core.message.help.legacy.more_information",
                prefix=msg.prefixes[0]))
        if Config('help_url'):
            help_msg.append(
                msg.locale.t(
                    "core.message.help.more_information.document",
                    url=Config('help_url')))
        if Config('donate_url'):
            help_msg.append(
                msg.locale.t(
                    "core.message.help.more_information.donate",
                    url=Config('donate_url')))
        await msg.finish('\n'.join(help_msg))
