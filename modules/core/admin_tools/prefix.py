from core.builtins.bot import Bot
from core.builtins.message.internal import I18NContext
from core.builtins.utils import command_prefix
from modules.core.common_tools.setup import setup


@setup.command("prefix list {{I18N:core.help.setup.prefix.list}}")
@setup.command(
    [
        "prefix add <prefix> {{I18N:core.help.setup.prefix.add}}",
        "prefix remove <prefix> {{I18N:core.help.setup.prefix.remove}}",
        "prefix reset {{I18N:core.help.setup.prefix.reset}}",
    ],
    required_admin=True,
)
async def _(msg: Bot.MessageSession):
    prefixes = msg.session_info.target_union_info.target_data.get("command_prefix")
    prefix = msg.parsed_msg.get("<prefix>", False)
    if not prefixes:
        prefixes = []
    if "add" in msg.parsed_msg:
        if prefix:
            if prefix not in prefixes:
                prefixes.append(prefix)
                await msg.session_info.target_union_info.edit_target_data("command_prefix", prefixes)
                await msg.finish(I18NContext("core.message.setup.prefix.add.success", prefix=prefix))
            else:
                await msg.finish(I18NContext("core.message.setup.prefix.add.already"))
    elif "remove" in msg.parsed_msg:
        if prefix:
            if prefix in prefixes:
                prefixes.remove(prefix)
                await msg.session_info.target_union_info.edit_target_data("command_prefix", prefixes)
                await msg.finish(I18NContext("core.message.setup.prefix.remove.success", prefix=prefix))
            else:
                await msg.finish(I18NContext("core.message.setup.prefix.remove.not_found"))
    elif "reset" in msg.parsed_msg:
        await msg.session_info.target_union_info.edit_target_data("command_prefix", [])
        await msg.finish(I18NContext("core.message.setup.prefix.reset"))
    elif "list" in msg.parsed_msg:
        default_msg = I18NContext("core.message.setup.prefix.list.default", prefixes=", ".join(command_prefix))
        if len(prefixes) == 0:
            custom_msg = I18NContext("core.message.setup.prefix.list.custom.none")
        else:
            custom_msg = I18NContext("core.message.setup.prefix.list.custom", prefixes=", ".join(prefixes))
        await msg.finish([default_msg, custom_msg])
