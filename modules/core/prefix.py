from core.builtins import Bot
from core.builtins.utils import command_prefix
from core.component import module

p = module('prefix', required_admin=True, base=True, doc=True)


@p.command('add <prefix> {{core.help.prefix.add}}',
           'remove <prefix> {{core.help.prefix.remove}}',
           'reset {{core.help.prefix.reset}}',
           'list {{core.help.prefix.list}}')
async def set_prefix(msg: Bot.MessageSession):
    prefixes = msg.options.get('command_prefix')
    prefix = msg.parsed_msg.get('<prefix>', False)
    if not prefixes:
        prefixes = []
    if 'add' in msg.parsed_msg:
        if prefix:
            if prefix not in prefixes:
                prefixes.append(prefix)
                msg.data.edit_option('command_prefix', prefixes)
                await msg.finish(msg.locale.t("core.message.prefix.add.success", prefix=prefix))
            else:
                await msg.finish(msg.locale.t("core.message.prefix.add.already"))
    elif 'remove' in msg.parsed_msg:
        if prefix:
            if prefix in prefixes:
                prefixes.remove(prefix)
                msg.data.edit_option('command_prefix', prefixes)
                await msg.finish(msg.locale.t("core.message.prefix.remove.success", prefix=prefix))
            else:
                await msg.finish(msg.locale.t("core.message.prefix.remove.not_found"))
    elif 'reset' in msg.parsed_msg:
        msg.data.edit_option('command_prefix', [])
        await msg.finish(msg.locale.t("core.message.prefix.reset"))
    elif 'list' in msg.parsed_msg:
        default_msg = msg.locale.t('core.message.prefix.list.default', prefixes=', '.join(command_prefix))
        if len(prefixes) == 0:
            custom_msg = msg.locale.t("core.message.prefix.list.custom.none")
        else:
            custom_msg = msg.locale.t('core.message.prefix.list.custom', prefixes=', '.join(prefixes))
        await msg.finish(f"{default_msg}\n{custom_msg}")
