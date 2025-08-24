from copy import deepcopy

from core.builtins.bot import Bot
from core.builtins.message.internal import I18NContext, Plain
from core.builtins.parser.command import CommandParser
from core.component import module
from core.config import Config, CFGManager
from core.constants.exceptions import InvalidHelpDocTypeError
from core.i18n import load_locale_file
from core.loader import ModulesManager, current_unloaded_modules, err_modules
from .help import modules_list_help

m = module(
    "module",
    base=True,
    alias={
        "enable": "module enable",
        "disable": "module disable",
        "load": "module load",
        "reload": "module reload",
        "unload": "module unload",
    },
    doc=True
)


@m.command(
    ["reload <module> ...",
     "load <module> ...",
     "unload <module> ..."
     ],
    required_superuser=True
)
@m.command("list [--legacy] {{I18N:core.help.module.list}}",
           options_desc={"--legacy": "{I18N:help.option.legacy}"}
           )
@m.command(
    ["enable <module>... {{I18N:core.help.module.enable}}",
     "enable all {{I18N:core.help.module.enable_all}}",
     "disable <module>... {{I18N:core.help.module.disable}}",
     "disable all {{I18N:core.help.module.disable_all}}"
     ],
    required_admin=True
)
async def _(msg: Bot.MessageSession):
    if msg.parsed_msg.get("list", False):
        legacy = False
        if msg.parsed_msg.get("--legacy", False):
            legacy = True
        await modules_list_help(msg, legacy)
    await config_modules(msg)


async def config_modules(msg: Bot.MessageSession):
    is_superuser = msg.check_super_user()
    alias = ModulesManager.modules_aliases
    modules_ = ModulesManager.return_modules_list(
        target_from=msg.session_info.target_from,
        client_name=msg.session_info.client_name)
    enabled_modules_list = deepcopy(msg.session_info.target_info.modules)
    wait_config = [msg.parsed_msg.get("<module>")] + msg.parsed_msg.get("...", [])
    wait_config_list = []
    for module_ in wait_config:
        if module_ not in wait_config_list:
            if module_ in alias:
                wait_config_list.append(alias[module_].split()[0])
            elif not module_:
                continue
            else:
                wait_config_list.append(module_.split()[0])
    msglist = []
    recommend_modules_list = []
    recommend_modules_help_doc_list = []
    if msg.parsed_msg.get("enable", False):
        enable_list = []
        if msg.parsed_msg.get("all", False):
            for function in modules_:
                if function[0] == "_":
                    continue
                if (
                    modules_[function].base
                    or modules_[function].hidden
                    or modules_[function].required_superuser
                ):
                    continue
                if modules_[function].rss and not msg.session_info.support_rss:
                    continue
                enable_list.append(function)
        else:
            for module_ in wait_config_list:
                if module_ not in modules_:
                    msglist.append(I18NContext("core.message.module.enable.not_found", module=module_))
                else:
                    if modules_[module_].required_superuser and not is_superuser:
                        msglist.append(I18NContext("parser.superuser.permission.denied"))
                    elif modules_[module_].base:
                        msglist.append(I18NContext("core.message.module.enable.already", module=module_))
                    elif modules_[module_].rss and not msg.session_info.support_rss:
                        msglist.append(I18NContext("core.message.module.enable.unsupported_rss"))
                    else:
                        enable_list.append(module_)
                        recommend = modules_[module_].recommend_modules
                        if recommend:
                            for r in recommend:
                                if r not in enable_list and r not in enabled_modules_list:
                                    recommend_modules_list.append(r)
        if await msg.session_info.target_info.config_module(enable_list, True):
            for x in enable_list:
                if x in enabled_modules_list:
                    msglist.append(I18NContext("core.message.module.enable.already", module=x))
                else:
                    msglist.append(I18NContext("core.message.module.enable.success", module=x))
                    support_lang = modules_[x].support_languages
                    if support_lang:
                        if msg.session_info.locale.locale not in support_lang:
                            msglist.append(I18NContext("core.message.module.unsupported_language", module=x))
        if recommend_modules_list:
            for m in recommend_modules_list:
                try:
                    recommend_modules_help_doc_list.append(I18NContext("core.message.module.recommends.help", module=m))

                    if modules_[m].desc:
                        recommend_modules_help_doc_list.append(
                            Plain(msg.session_info.locale.t_str(modules_[m].desc))
                        )
                    hdoc = CommandParser(
                        modules_[m],
                        msg=msg,
                        bind_prefix=modules_[m].bind_prefix,
                        command_prefixes=msg.session_info.prefixes,
                        is_superuser=is_superuser,
                    ).return_formatted_help_doc()
                    recommend_modules_help_doc_list.append(Plain(hdoc))
                except InvalidHelpDocTypeError:
                    pass
    elif msg.parsed_msg.get("disable", False):
        disable_list = []
        if msg.parsed_msg.get("all", False):
            for function in modules_:
                if function[0] == "_":
                    continue
                if modules_[function].base or modules_[function].hidden or modules_[function].required_superuser:
                    continue
                disable_list.append(function)
        else:
            for module_ in wait_config_list:
                if module_ not in modules_:
                    msglist.append(I18NContext("core.message.module.disable.not_found", module=module_))
                else:
                    if modules_[module_].required_superuser and not is_superuser:
                        msglist.append(I18NContext("parser.superuser.permission.denied"))
                    elif modules_[module_].base:
                        msglist.append(I18NContext("core.message.module.disable.base", module=module_))
                    else:
                        disable_list.append(module_)

        if await msg.session_info.target_info.config_module(disable_list, False):
            for x in disable_list:
                if x not in enabled_modules_list:
                    msglist.append(I18NContext("core.message.module.disable.already", module=x))
                else:
                    msglist.append(I18NContext("core.message.module.disable.success", module=x))
    elif msg.parsed_msg.get("reload", False):

        async def module_reload(module, extra_modules, base_module=False):
            reload_count = await ModulesManager.reload_module(module)
            if base_module and reload_count >= 1:
                return I18NContext("core.message.module.reload.base.success")
            if reload_count > 1:
                return Plain(
                    str(I18NContext("core.message.module.reload.success", module=module))
                    + ("\n" if len(extra_modules) != 0 else "")
                    + "\n".join(extra_modules)
                    + "\n"
                    + str(I18NContext("core.message.module.reload.with", reload_count=reload_count - 1))
                )
            if reload_count == 1:
                return Plain(
                    str(I18NContext("core.message.module.reload.success", module=module))
                    + ("\n" if len(extra_modules) != 0 else "")
                    + "\n".join(extra_modules)
                    + "\n"
                    + str(I18NContext("core.message.module.reload.no_more"))
                )
            return I18NContext("core.message.module.reload.failed")

        for module_ in wait_config_list:
            base_module = False
            if module_ not in modules_:
                msglist.append(I18NContext("core.message.module.reload.not_found", module=module_))
            else:
                extra_reload_modules = ModulesManager.search_related_module(module_, False)
                if modules_[module_].base:
                    if Config("allow_reload_base", False):
                        if await msg.wait_confirm(
                            I18NContext("core.message.module.reload.base.confirm"),
                            append_instruction=False,
                        ):
                            base_module = True
                        else:
                            await msg.finish()
                    else:
                        await msg.finish(I18NContext("core.message.module.reload.base.failed", module=module_))

                elif extra_reload_modules:
                    if not await msg.wait_confirm(
                        I18NContext("core.message.module.reload.confirm", modules="\n".join(extra_reload_modules)),
                        append_instruction=False,
                    ):
                        await msg.finish()
                unloaded_list = CFGManager.get("unloaded_modules", [])
                if unloaded_list and module_ in unloaded_list:
                    unloaded_list.remove(module_)
                    CFGManager.write("unloaded_modules", unloaded_list)
                msglist.append(await module_reload(module_, extra_reload_modules, base_module))

        locale_err = load_locale_file()
        if len(locale_err) != 0:
            msglist.append(I18NContext("core.message.locale.reload.failed"))
            msglist.append(Plain("\n".join(locale_err), disable_joke=True))
    elif msg.parsed_msg.get("load", False):
        for module_ in wait_config_list:
            if module_ not in current_unloaded_modules:
                msglist.append(I18NContext("core.message.module.load.not_found"))
                continue
            if await ModulesManager.load_module(module_):
                msglist.append(I18NContext("core.message.module.load.success", module=module_)
                               )
                unloaded_list = CFGManager.get("unloaded_modules", [])
                if unloaded_list and module_ in unloaded_list:
                    unloaded_list.remove(module_)
                    CFGManager.write("unloaded_modules", unloaded_list)
            else:
                msglist.append(I18NContext("core.message.module.load.failed"))

    elif msg.parsed_msg.get("unload", False):
        for module_ in wait_config_list:
            if module_ not in modules_:
                if module_ in err_modules:
                    if await msg.wait_confirm(I18NContext("core.message.module.unload.unavailable.confirm"),
                                              append_instruction=False):
                        unloaded_list = CFGManager.get("unloaded_modules", [])
                        if not unloaded_list:
                            unloaded_list = []
                        if module_ not in unloaded_list:
                            unloaded_list.append(module_)
                            CFGManager.write("unloaded_modules", unloaded_list)
                        msglist.append(I18NContext("core.message.module.unload.success", module=module_))
                        err_modules.remove(module_)
                        current_unloaded_modules.append(module_)
                    else:
                        await msg.finish()
                else:
                    msglist.append(I18NContext("core.message.module.unload.not_found"))
                continue
            if modules_[module_].base:
                msglist.append(I18NContext("core.message.module.unload.base", module=module_))
                continue
            if await msg.wait_confirm(I18NContext("core.message.module.unload.confirm"),
                                      append_instruction=False):
                if await ModulesManager.unload_module(module_):
                    msglist.append(I18NContext("core.message.module.unload.success", module=module_))
                    unloaded_list = CFGManager.get("unloaded_modules", [])
                    if not unloaded_list:
                        unloaded_list = []
                    unloaded_list.append(module_)
                    CFGManager.write("unloaded_modules", unloaded_list)
            else:
                await msg.finish()

    if msglist:
        if not recommend_modules_help_doc_list:
            await msg.finish(msglist)
        else:
            await msg.send_message(msglist)
    if recommend_modules_help_doc_list:
        if await msg.wait_confirm(
            [I18NContext("core.message.module.recommends", modules="\n".join(recommend_modules_list)),
             Plain("\n")] + recommend_modules_help_doc_list):
            if await msg.session_info.target_info.config_module(recommend_modules_list, True):
                msglist = []
                for x in recommend_modules_list:
                    msglist.append(I18NContext("core.message.module.enable.success", module=x))
                await msg.finish(msglist)
        else:
            await msg.finish()
    else:
        return
