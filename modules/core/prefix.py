from core.builtins import Bot
from core.component import module

p = module('prefix', required_admin=True, base=True)


@p.command('add <prefix> {{core.prefix.help.add}}',
           'remove <prefix> {{core.prefix.help.remove}}',
           'reset {{core.prefix.help.reset}}')
async def set_prefix(msg: Bot.MessageSession):
    prefixes = msg.options.get('command_prefix')
    arg1 = msg.parsed_msg.get('<prefix>', False)
    if prefixes is None:
        prefixes = []
    if 'add' in msg.parsed_msg:
        if arg1:
            if arg1 not in prefixes:
                prefixes.append(arg1)
                msg.data.edit_option('command_prefix', prefixes)
                await msg.sendMessage(msg.locale.t("core.prefix.message.add.success", prefix=arg1))
            else:
                await msg.sendMessage(msg.locale.t("core.prefix.message.add.already"))
    elif 'remove' in msg.parsed_msg:
        if arg1:
            if arg1 in prefixes:
                prefixes.remove(arg1)
                msg.data.edit_option('command_prefix', prefixes)
                await msg.sendMessage(msg.locale.t("core.prefix.message.remove.success") + arg1)
            else:
                await msg.sendMessage(msg.locale.t("core.prefix.message.remove.not_found"))
    elif 'reset' in msg.parsed_msg:
        msg.data.edit_option('command_prefix', [])
        await msg.sendMessage(msg.locale.t("core.prefix.message.reset"))
    elif 'list' in msg.parsed_msg:
        if len(prefixes) == 0:
            await msg.sendMessage(msg.locale.t("core.prefix.message.list.none"))
        else:
            await msg.finish(msg.locale.t('core.prefix.message.list', prefixes=', '.join(prefixes)))