import re

from core.builtins.bot import Bot
from core.builtins.message.internal import Image, I18NContext, Plain
from core.component import module
from core.utils.image_table import image_table_render, ImageTable

ali = module("alias", base=True, doc=True)


@ali.command(
    "list [--legacy] {{I18N:core.help.alias.list}}",
    options_desc={"--legacy": "{I18N:help.option.legacy}"},
)
@ali.command([
    "add <alias> <command> {{I18N:core.help.alias.add}}",
    "remove <alias> {{I18N:core.help.alias.remove}}",
    "reset {{I18N:core.help.alias.reset}}",
    "raise <alias> {{I18N:core.help.alias.raise}}",
    "lower <alias> {{I18N:core.help.alias.lower}}"
], required_admin=True)
async def _(msg: Bot.MessageSession):
    aliases = msg.session_info.target_info.target_data.get("command_alias")
    alias = msg.parsed_msg.get("<alias>", False)
    command = msg.parsed_msg.get("<command>", False)
    if not aliases:
        aliases = {}
    if "add" in msg.parsed_msg:
        # 处理下划线与空格的情况
        alias = re.sub(
            r"\$\{([^}]*)\}",
            lambda match: "${" + match.group(1).replace(" ", "_") + "}",
            alias.replace("_", " "),
        )
        command = re.sub(
            r"\$\{([^}]*)\}",
            lambda match: "${" + match.group(1).replace(" ", "_") + "}",
            command,
        )

        if not (check_valid_placeholder(alias) and check_valid_placeholder(command)):
            await msg.finish(I18NContext("core.message.alias.add.invalid_placeholder"))
        if alias not in aliases:
            has_prefix = False
            for prefixes in msg.session_info.prefixes:
                if command.startswith(prefixes):
                    has_prefix = True
                    break
            if not has_prefix:
                await msg.finish(I18NContext("core.message.alias.add.invalid_prefix"))
            aliases[alias] = command[1:]
            await msg.session_info.target_info.edit_target_data("command_alias", aliases)
            await msg.finish(I18NContext("core.message.alias.add.success", alias=alias, command=command))
        else:
            await msg.finish(I18NContext("core.message.alias.add.already", alias=alias))
    elif "remove" in msg.parsed_msg:
        alias = re.sub(
            r"\$\{([^}]*)\}",
            lambda match: "${" + match.group(1).replace(" ", "_") + "}",
            alias.replace("_", " "),
        )
        if alias in aliases:
            del aliases[alias]
            await msg.session_info.target_info.edit_target_data("command_alias", aliases)
            await msg.finish(I18NContext("core.message.alias.remove.success", alias=alias))
        else:
            await msg.finish(I18NContext("core.message.alias.not_found", alias=alias))
    elif "reset" in msg.parsed_msg:
        await msg.session_info.target_info.edit_target_data("command_alias", {})
        await msg.finish(I18NContext("core.message.alias.reset.success"))
    elif "raise" in msg.parsed_msg:
        alias = alias.replace("_", " ")
        alias = re.sub(
            r"\$\{([^}]*)\}",
            lambda match: "${" + match.group(1).replace(" ", "_") + "}",
            alias,
        )
        if alias not in aliases:
            await msg.finish(I18NContext("core.message.alias.not_found", alias=alias))

        aliases_list = list(aliases.items())
        index = next((i for i, (k, _) in enumerate(aliases_list) if k == alias), None)
        if index is not None and index > 0:
            aliases_list[index - 1], aliases_list[index] = aliases_list[index], aliases_list[index - 1]
            new_aliases = dict(aliases_list)
            await msg.session_info.target_info.edit_target_data("command_alias", new_aliases)
            priority = len(new_aliases) - (index - 1)
            await msg.finish(I18NContext("core.message.alias.raise.success", alias=alias, priority=priority))
        else:
            await msg.finish(I18NContext("core.message.alias.raise.failed", alias=alias))
    elif "lower" in msg.parsed_msg:
        alias = alias.replace("_", " ")
        alias = re.sub(
            r"\$\{([^}]*)\}",
            lambda match: "${" + match.group(1).replace(" ", "_") + "}",
            alias,
        )
        if alias not in aliases:
            await msg.finish(I18NContext("core.message.alias.not_found", alias=alias))

        aliases_list = list(aliases.items())
        index = next((i for i, (k, _) in enumerate(aliases_list) if k == alias), None)
        if index is not None and index < len(aliases_list) - 1:
            aliases_list[index], aliases_list[index + 1] = aliases_list[index + 1], aliases_list[index]
            new_aliases = dict(aliases_list)
            await msg.session_info.target_info.edit_target_data("command_alias", new_aliases)
            priority = len(new_aliases) - (index + 1)
            await msg.finish(I18NContext("core.message.alias.lower.success", alias=alias, priority=priority))
        else:
            await msg.finish(I18NContext("core.message.alias.lower.failed", alias=alias))
    elif "list" in msg.parsed_msg:
        aliases_count = len(list(aliases.keys()))
        legacy = True
        if len(aliases) == 0:
            await msg.finish(I18NContext("core.message.alias.list.none"))
        elif not msg.parsed_msg.get("--legacy", False):
            table = ImageTable(
                [
                    [str(aliases_count - i), k, msg.session_info.prefixes[0] + aliases[k]]
                    for i, k in enumerate(aliases)
                ],
                [
                    "{I18N:core.message.alias.list.table.header.priority}",
                    "{I18N:core.message.alias.list.table.header.alias}",
                    "{I18N:core.message.alias.list.table.header.command}",
                ],
                msg.session_info
            )
            imgs = await image_table_render(table)
            if imgs:
                legacy = False
                img_lst = []
                for img in imgs:
                    img_lst.append(Image(img))
                await msg.finish([I18NContext("core.message.alias.list")] + img_lst)
            else:
                pass

        if legacy:
            await msg.finish([I18NContext("core.message.alias.list"),
                              Plain("\n".join(
                                  [f"{aliases_count - i} - {k} -> {msg.session_info.prefixes[0]}{aliases[k]}" for i, k
                                   in enumerate(aliases)]))])


def check_valid_placeholder(alias):
    """检查占位符有效性"""
    alias_noph = alias
    phs = re.findall(r"\${(.*?)}", alias)
    for ph in phs:
        if not ph or "$" in ph or "}" in ph or "{" in ph:
            return False
        alias_noph = alias_noph.replace(f"${{{ph}}}", "")
    return alias_noph.strip()
