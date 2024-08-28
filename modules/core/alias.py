import re

from core.builtins import Bot, Image
from core.component import module
from core.utils.image_table import image_table_render, ImageTable

ali = module('alias', required_admin=True, base=True, doc=True)


@ali.command('add <alias> <command> {{core.help.alias.add}}',
             'remove <alias> {{core.help.alias.remove}}',
             'reset {{core.help.alias.reset}}',
             'raise <alias> {{core.help.alias.raise}}',
             'lower <alias> {{core.help.alias.lower}}',
             'list [--legacy] {{core.help.alias.list}}',
             options_desc={'--legacy': '{help.option.legacy}'})
async def set_alias(msg: Bot.MessageSession):
    aliases = msg.options.get('command_alias')
    alias = msg.parsed_msg.get('<alias>', False)
    command = msg.parsed_msg.get('<command>', False)
    if not aliases:
        aliases = {}
    if 'add' in msg.parsed_msg:
        # 处理下划线与空格的情况
        alias = alias.replace('_', ' ')
        alias = re.sub(r'\$\{([^}]*)\}', lambda match: '${' + match.group(1).replace(' ', '_') + '}', alias)
        command = re.sub(r'\$\{([^}]*)\}', lambda match: '${' + match.group(1).replace(' ', '_') + '}', command)
        # 检查占位符有效性

        def check_valid_placeholder(alias):
            alias_noph = alias
            phs = re.findall(r"\${(.*?)}", alias)
            for ph in phs:
                if not ph or '$' in ph or '}' in ph or '{' in ph:
                    return False
                alias_noph = alias_noph.replace(f"${{{ph}}}", "")
            return alias_noph.strip()

        if not (check_valid_placeholder(alias) and check_valid_placeholder(command)):
            await msg.finish(msg.locale.t("core.message.alias.add.invalid_placeholder"))
        if alias not in aliases:
            has_prefix = False
            for prefixes in msg.prefixes:
                if command.startswith(prefixes):
                    has_prefix = True
                    break
            if not has_prefix:
                await msg.finish(msg.locale.t("core.message.alias.add.invalid_prefix"))
            aliases[alias] = command[1:]
            msg.data.edit_option('command_alias', aliases)
            await msg.finish(msg.locale.t("core.message.alias.add.success", alias=alias, command=command))
        else:
            await msg.finish(msg.locale.t("core.message.alias.add.already", alias=alias))
    elif 'remove' in msg.parsed_msg:
        alias = alias.replace('_', ' ').replace('${ }', '${_}')
        if alias in aliases:
            del aliases[alias]
            msg.data.edit_option('command_alias', aliases)
            await msg.finish(msg.locale.t("core.message.alias.remove.success", alias=alias))
        else:
            await msg.finish(msg.locale.t("core.message.alias.not_found", alias=alias))
    elif 'reset' in msg.parsed_msg:
        msg.data.edit_option('command_alias', {})
        await msg.finish(msg.locale.t("core.message.alias.reset.success"))
    elif 'raise' in msg.parsed_msg:
        alias = alias.replace('_', ' ')
        alias = re.sub(r'\$\{([^}]*)\}', lambda match: '${' + match.group(1).replace(' ', '_') + '}', alias)
        if alias not in aliases:
            await msg.finish(msg.locale.t("core.message.alias.not_found", alias=alias))
        aliases_list = list(aliases.keys())
        index = aliases_list.index(alias)
        new_index = index - 1 if index > 0 else None
        if new_index is not None:
            aliases_list.pop(index)
            aliases_list.insert(new_index, alias)
            msg.data.edit_option('command_alias', {k: aliases[k] for k in aliases_list})
            priority = len(aliases_list) - new_index
            await msg.finish(msg.locale.t("core.message.alias.raise.success", alias=alias, priority=priority))
        else:
            await msg.finish(msg.locale.t("core.message.alias.raise.failed", alias=alias))
    elif 'lower' in msg.parsed_msg:
        alias = alias.replace('_', ' ')
        alias = re.sub(r'\$\{([^}]*)\}', lambda match: '${' + match.group(1).replace(' ', '_') + '}', alias)
        if alias not in aliases:
            await msg.finish(msg.locale.t("core.message.alias.not_found", alias=alias))
        aliases_list = list(aliases.keys())
        index = aliases_list.index(alias)
        new_index = index + 1 if index < len(aliases_list) - 1 else None
        if new_index:
            aliases_list.pop(index)
            aliases_list.insert(new_index, alias)
            msg.data.edit_option('command_alias', {k: aliases[k] for k in aliases_list})
            priority = len(aliases_list) - new_index
            await msg.finish(msg.locale.t("core.message.alias.lower.success", alias=alias, priority=priority))
        else:
            await msg.finish(msg.locale.t("core.message.alias.lower.failed", alias=alias))
    elif 'list' in msg.parsed_msg:
        aliases_count = len(list(aliases.keys()))
        legacy = True
        if len(aliases) == 0:
            await msg.finish(msg.locale.t("core.message.alias.list.none"))
        elif not msg.parsed_msg.get('--legacy', False):
            table = ImageTable([[str(aliases_count - i),
                                 k,
                                 msg.prefixes[0] + aliases[k]] for i,
                                k in enumerate(aliases)],
                               [msg.locale.t("core.message.alias.list.table.header.priority"),
                                msg.locale.t("core.message.alias.list.table.header.alias"),
                                msg.locale.t("core.message.alias.list.table.header.command")])
            img = await image_table_render(table)
            if img:
                legacy = False
                await msg.finish([msg.locale.t("core.message.alias.list"), Image(img)])
            else:
                pass

        if legacy:
            await msg.finish(f'{msg.locale.t("core.message.alias.list")}\n'
                             + '\n'.join([f'{aliases_count - i} - {k} -> {msg.prefixes[0]}{aliases[k]}' for i, k in enumerate(aliases)]))
