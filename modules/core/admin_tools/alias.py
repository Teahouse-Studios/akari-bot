import re
from string import Template as StringTemplate

from core.builtins.bot import Bot
from core.builtins.message.internal import Image, I18NContext, Plain
from core.builtins.parser.hooks import HookPoint
from core.logger import Logger
from core.utils.image_table import image_table_render, ImageTable
from modules.core.common_tools.setup import setup


def transform_alias(command: str, aliases: dict[str, str], prefix: str) -> str:
    """按场景自定义规则改写命令文本。"""
    matched_aliases = []
    for pattern, replacement in aliases.items():
        if not re.search(r"\${[^}]*}", pattern):
            continue
        normalized_pattern = re.sub(r"(\$\{\w+})(?=\$\{\w+})", r"\1 ", pattern)
        placeholders = re.findall(r"\$\{([^{}$]+)}", normalized_pattern)
        regex_pattern = re.escape(normalized_pattern)
        for placeholder in placeholders:
            regex_pattern = regex_pattern.replace(re.escape(f"${{{placeholder}}}"), r"(\S+)")
        if match := re.match(regex_pattern, command):
            matched_aliases.append((len(placeholders), replacement, placeholders, match))

    if matched_aliases:
        _, replacement, placeholders, match = max(matched_aliases, key=lambda item: item[0])
        values = dict(zip(placeholders, match.groups()))
        return prefix + StringTemplate(replacement).safe_substitute(values)

    for pattern, replacement in aliases.items():
        if not re.search(r"\${[^}]*}", pattern) and command.startswith(pattern):
            return command.replace(pattern, prefix + replacement, 1)
    return command


@setup.hook(point=HookPoint.MESSAGE_NORMALIZED, priority=10, name="rewrite", server_scope=True)
async def _(ctx: Bot.ParserHookContext):
    info = ctx.msg.session_info
    target = info.target_union_info
    aliases = target.target_data.get("command_alias", {}) if target else {}
    if not aliases or not info.prefixes:
        return None
    trigger_msg = transform_alias(ctx.trigger_msg, dict(aliases), info.prefixes[0])
    if trigger_msg == ctx.trigger_msg:
        return None
    Logger.debug(trigger_msg)
    return ctx.RewriteTrigger(trigger_msg)


@setup.command(
    "alias list [--legacy] {{I18N:core.help.alias.list}}",
    options_desc={"--legacy": "{I18N:help.option.legacy}"},
)
@setup.command(
    [
        "alias add <alias> <command> {{I18N:core.help.alias.add}}",
        "alias remove <alias> {{I18N:core.help.alias.remove}}",
        "alias reset {{I18N:core.help.alias.reset}}",
    ],
    required_admin=True,
)
async def _(msg: Bot.MessageSession):
    aliases = msg.session_info.target_union_info.target_data.get("command_alias")
    alias = msg.parsed_msg.get("<alias>", False)
    command = msg.parsed_msg.get("<command>", False)
    if not aliases:
        aliases = {}
    if "add" in msg.parsed_msg:
        # 处理下划线与空格的情况
        alias = re.sub(r"_", " ", alias)
        alias = re.sub(r"\\ ", "_", alias)

        alias = re.sub(
            r"\$\{([^}]*)\}",
            lambda match: "${" + match.group(1) + "}",
            alias,
        )
        command = re.sub(
            r"\$\{([^}]*)\}",
            lambda match: "${" + match.group(1) + "}",
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
            await msg.session_info.target_union_info.edit_target_data("command_alias", aliases)
            await msg.finish(I18NContext("core.message.alias.add.success", alias=alias, command=command))
        else:
            await msg.finish(I18NContext("core.message.alias.add.already", alias=alias))
    elif "remove" in msg.parsed_msg:
        alias = re.sub(r"_", " ", alias)
        alias = re.sub(r"\\ ", "_", alias)
        alias = re.sub(
            r"\$\{([^}]*)\}",
            lambda match: "${" + match.group(1) + "}",
            alias,
        )
        if alias in aliases:
            del aliases[alias]
            await msg.session_info.target_union_info.edit_target_data("command_alias", aliases)
            await msg.finish(I18NContext("core.message.alias.remove.success", alias=alias))
        else:
            await msg.finish(I18NContext("core.message.alias.not_found", alias=alias))
    elif "reset" in msg.parsed_msg:
        await msg.session_info.target_union_info.edit_target_data("command_alias", {})
        await msg.finish(I18NContext("core.message.alias.reset.success"))
    elif "list" in msg.parsed_msg:
        legacy = True
        if len(aliases) == 0:
            await msg.finish(I18NContext("core.message.alias.list.none"))
        elif not msg.parsed_msg.get("--legacy", False):
            table = ImageTable(
                [[k, msg.session_info.prefixes[0] + aliases[k]] for i, k in enumerate(aliases)],
                [
                    "{I18N:core.message.alias.list.table.header.alias}",
                    "{I18N:core.message.alias.list.table.header.command}",
                ],
                msg.session_info,
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
            await msg.finish(
                [I18NContext("core.message.alias.list")]
                + [Plain(f"{k} -> {msg.session_info.prefixes[0]}{aliases[k]}") for i, k in enumerate(aliases)]
            )


def check_valid_placeholder(alias):
    alias_noph = alias
    phs = re.findall(r"\${(.*?)}", alias)
    for ph in phs:
        if not ph or "$" in ph or "}" in ph or "{" in ph:
            return False
        alias_noph = alias_noph.replace(f"${{{ph}}}", "")
    return alias_noph.strip()
