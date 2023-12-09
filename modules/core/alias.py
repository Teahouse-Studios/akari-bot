from core.builtins import Bot, Image, command_prefix
from core.component import module
from core.utils.image_table import image_table_render, ImageTable

ali = module('alias', required_admin=True, base=True)


@ali.command('add <alias> <command> {{core.help.alias.add}}',
             'remove <alias> {{core.help.alias.remove}}',
             'reset {{core.help.alias.reset}}',
             'list {{core.help.alias.list}}',
             'list legacy {{core.help.alias.list.legacy}}')
async def set_alias(msg: Bot.MessageSession):
    aliases = msg.options.get('command_alias')
    alias = msg.parsed_msg.get('<alias>', False)
    command = msg.parsed_msg.get('<command>', False)
    if aliases is None:
        aliases = {}
    if 'add' in msg.parsed_msg:
        if alias not in aliases:
            has_prefix = False
            for prefixes in msg.prefixes:
                if command.startswith(prefixes):
                    has_prefix = True
                    break
            if not has_prefix:
                await msg.finish(msg.locale.t("core.message.alias.add.invalid_prefix"))
            command = command_prefix[0] + command[1:]
            aliases[alias] = command
            msg.data.edit_option('command_alias', aliases)
            await msg.finish(msg.locale.t("core.message.alias.add.success", alias=alias, command=command))
        else:
            await msg.finish(msg.locale.t("core.message.alias.add.already", alias=alias))
    elif 'remove' in msg.parsed_msg:
        if alias in aliases:
            del aliases[alias]
            msg.data.edit_option('command_alias', aliases)
            await msg.finish(msg.locale.t("core.message.alias.remove.success", alias=alias))
        else:
            await msg.finish(msg.locale.t("core.message.alias.remove.not_found", alias=alias))
    elif 'reset' in msg.parsed_msg:
        msg.data.edit_option('command_alias', {})
        await msg.finish(msg.locale.t("core.message.alias.reset.success"))
    elif 'list' in msg.parsed_msg:
        legacy = True
        if len(aliases) == 0:
            await msg.finish(msg.locale.t("core.message.alias.list.none"))
        elif 'list' not in msg.parsed_msg:
            table = ImageTable([[k, aliases[k]] for k in aliases],
                               [msg.locale.t("core.message.alias.list.table.header.alias"),
                                msg.locale.t("core.message.alias.list.table.header.command")])
            img = await image_table_render(table)
            if img:
                legacy = False
                await msg.finish([msg.locale.t("core.message.alias.list"), Image(img)])
            else:
                pass
        
        if legacy:
                await msg.finish(f'{msg.locale.t("core.message.alias.list")}\n'
                                       + '\n'.join([f'{k} -> {aliases[k]}' for k in aliases]))
