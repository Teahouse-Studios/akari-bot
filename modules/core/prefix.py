from core.builtins import Bot, I18NContext
from core.builtins.utils import command_prefix
from core.component import module

p = module("prefix", base=True, doc=True)


@p.command("list {[I18N:core.help.prefix.list]}")
@p.command([
    "add <prefix> {[I18N:core.help.prefix.add]}",
    "remove <prefix> {[I18N:core.help.prefix.remove]}",
    "reset {[I18N:core.help.prefix.reset]}"
], required_admin=True)
async def _(msg: Bot.MessageSession):
    prefixes = msg.target_data.get("command_prefix")
    prefix = msg.parsed_msg.get("<prefix>", False)
    if not prefixes:
        prefixes = []
    if "add" in msg.parsed_msg:
        if prefix:
            if prefix not in prefixes:
                prefixes.append(prefix)
                await msg.target_info.edit_target_data("command_prefix", prefixes)
                await msg.finish(I18NContext("core.message.prefix.add.success", prefix=prefix))
            else:
                await msg.finish(I18NContext("core.message.prefix.add.already"))
    elif "remove" in msg.parsed_msg:
        if prefix:
            if prefix in prefixes:
                prefixes.remove(prefix)
                await msg.target_info.edit_target_data("command_prefix", prefixes)
                await msg.finish(I18NContext("core.message.prefix.remove.success", prefix=prefix))
            else:
                await msg.finish(I18NContext("core.message.prefix.remove.not_found"))
    elif "reset" in msg.parsed_msg:
        await msg.target_info.edit_target_data("command_prefix", [])
        await msg.finish(I18NContext("core.message.prefix.reset"))
    elif "list" in msg.parsed_msg:
        default_msg = I18NContext("core.message.prefix.list.default", prefixes=", ".join(command_prefix))
        if len(prefixes) == 0:
            custom_msg = I18NContext("core.message.prefix.list.custom.none")
        else:
            custom_msg = I18NContext("core.message.prefix.list.custom", prefixes=", ".join(prefixes))
        await msg.finish([default_msg, custom_msg])
