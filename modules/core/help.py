import re
from dataclasses import dataclass
from html import escape

from jinja2 import FileSystemLoader, Environment

from core.builtins.bot import Bot
from core.builtins.message.chain import MessageChain
from core.builtins.message.elements import ButtonRows, ImageElement
from core.builtins.message.internal import ActionText, ButtonFrame, I18NContext, Plain, Url
from core.builtins.parser.command import CommandParser
from core.builtins.utils import command_prefix
from core.component import module
from core.config.base import CoreConfig
from core.constants.path import templates_path
from core.loader import ModulesManager
from core.logger import Logger
from core.utils.button import arrange_buttons
from core.utils.cache import random_cache_path
from core.utils.image import cb64imglst
from core.utils.table import escape_table_cell, format_table_code, resolve_table_columns
from core.web_render import web_render, ElementScreenshotOptions
from .utils import get_version_display

env = Environment(loader=FileSystemLoader(templates_path), autoescape=True, enable_async=True)
help_url = CoreConfig.help_url
donate_url = CoreConfig.donate_url
use_font_mirror = CoreConfig.use_font_mirror

hlp = module("help", base=True, doc=True)


@dataclass(frozen=True)
class ModuleListEntry:
    name: str
    enabled: bool
    subscription: bool = False
    unsupported: bool = False


def is_module_entry(item) -> bool:
    return all(hasattr(item, field) for field in ("name", "enabled", "subscription", "unsupported"))


def create_module_entry(module_, name: str, enabled_modules: list[str] | None, session_info) -> ModuleListEntry:
    return ModuleListEntry(
        name=name,
        enabled=module_.base or name in (enabled_modules or []),
        subscription=module_.rss,
        unsupported=bool(module_.unsupported_reason(session_info)),
    )


def get_module_toggle(entry: ModuleListEntry, prefix: str) -> tuple[str, str]:
    if entry.subscription:
        emoji = "🔔" if entry.enabled else "🔕"
    else:
        emoji = "🔓" if entry.enabled else "🔐"
    action = "disable" if entry.enabled else "enable"
    return emoji, f"{prefix}{action} {entry.name}"


def format_module_entries(entries: list[str | ModuleListEntry]) -> str:
    rendered = []
    for item in entries:
        if is_module_entry(item):
            emoji, _ = get_module_toggle(item, "")
            name = f"~~{item.name}~~" if item.unsupported else item.name
            rendered.append(f"{emoji} {name}")
        else:
            rendered.append(item)
    return " | ".join(rendered)


def has_unsupported_entries(groups: list[tuple[str, list[str | ModuleListEntry]]]) -> bool:
    return any(is_module_entry(item) and item.unsupported for _, entries in groups for item in entries)


def qqbot_permissions_limited(msg: Bot.MessageSession) -> bool:
    return msg.session_info.client_name == "QQBot" and not (
        msg.session_info.support_rss and msg.session_info.read_all_messages
    )


def split_subscription_modules(module_list: dict, names: list[str]) -> tuple[list[str], list[str]]:
    """按模块的 RSS 标记拆分普通模块与订阅模块，并保持原有顺序。"""
    regular = []
    subscription = []
    for name in names:
        (subscription if module_list[name].rss else regular).append(name)
    return regular, subscription


def get_module_type_display(module_, locale) -> str:
    """返回适合 Markdown 详情页展示的模块类型标记。"""
    if module_.base:
        emoji = "🟧"
        type_key = "core.message.help.table.base"
    elif module_.rss:
        emoji = "🟩"
        type_key = "core.message.help.table.subscription"
    else:
        emoji = "🟦"
        type_key = "core.message.help.table.external"
    return f"{emoji} {locale.t(type_key)}"


def get_regex_disable_prefix_display() -> str:
    prefixes = [prefix for prefix in CoreConfig.regex_disable_prefix if isinstance(prefix, str) and prefix]
    return " ".join(prefixes)


def should_use_markdown_table(msg: Bot.MessageSession, force_image: bool = False, force_legacy: bool = False) -> bool:
    return not force_image and not force_legacy and msg.session_info.support_markdown_table


def build_clickable_modules(msg: Bot.MessageSession, groups: list[tuple[str, list[str | ModuleListEntry]]]) -> list:
    """
    把若干组模块名构造成可点击的消息链片段。

    每个模块名成为一个指令操作元素，点击后向输入框填入 `<前缀>help <模块名>`，
    省去用户照着列表手动输入的一步。

    标题以纯文本构造并自带换行，而非交由 I18NContext 延迟翻译：适配器渲染时会把
    指令操作无条件拼入上一项，标题若不带换行，模块列表会被挤到标题同一行，
    与既有的纯文本版排版不符。同理，第二组起的标题还须带前导换行，
    否则会紧贴在上一组末尾的标签之后。

    :param msg: 消息会话。
    :param groups: (标题多语言键, 模块名列表) 的序列，模块名为空的组会被跳过。
    :return: 消息元素列表；所有组皆空时返回空片段，空态文案由调用方负责。
    """
    prefix = msg.session_info.prefixes[0]
    parts = []
    for title_key, names in groups:
        if not names:
            continue
        leading = "\n" if parts else ""
        parts.append(Plain(leading + msg.session_info.locale.t(title_key) + "\n", disable_joke=True))
        for index, item in enumerate(names):
            if index:
                parts.append(Plain(" | ", disable_joke=True))
            if is_module_entry(item):
                emoji, command = get_module_toggle(item, prefix)
                parts.append(ActionText(command, show=emoji))
                parts.append(Plain(" ~~" if item.unsupported else " ", disable_joke=True))
                parts.append(ActionText(f"{prefix}help {item.name}", show=item.name))
                if item.unsupported:
                    parts.append(Plain("~~", disable_joke=True))
            else:
                parts.append(ActionText(f"{prefix}help {item}", show=item))
    return parts


def end_inline_run(chain: MessageChain) -> None:
    """
    终止行内连排，使其后追加的元素能各自成行。

    可点击的模块列表以指令操作收尾，而适配器会把紧随指令操作之后的文本并入同一行
    （见 ``bots/qqbot/context.py`` 中 send_msg_markdown() 的 ``inline_pending``）。
    该规则本是为「文字 + 标签 + 收尾文字」这类同出一句话的场合而设，跨消息元素时却会
    把调用方随后追加的提示语粘在最后一个模块名之后。补一个纯文本片段即可断开连排。

    片段取一个空格而非空串：消息链会把空文本换成错误提示（见
    ``core/builtins/message/chain.py`` 对空文本的处理）。换行同样不可取——适配器随后
    仍会按元素补一次换行，两者叠加会多出一个空行。

    本函数只在具备指令操作能力的平台上有意义，调用点均已由 ``use_clickable`` 把关。

    :param chain: 待收尾的消息链，就地修改。
    """
    chain.append(Plain(" ", disable_joke=True))


def build_module_table(
    msg: Bot.MessageSession,
    groups: list[tuple[str, list[str | ModuleListEntry]]],
    include_help_header: bool = False,
    permission: str = "user",
) -> list:
    """
    把若干组模块名排成一张 markdown 表。

    各组同处一张表，组与组之间以一行只填组名的区隔行分开；首组的组名即表头。表格至多
    :data:`~core.utils.table.TABLE_MAX_ROWS` 行、至少 :data:`~core.utils.table.TABLE_MIN_COLUMNS` 列，
    模块数的增长由列数吸收。末行不足处补空单元格 —— markdown 要求各行的列数一致。

    ``include_help_header`` 开启时，机器人名、当前语言、版本与用户权限会成为同一张表的首行。
    此时表格至少使用四列，列数更多时在首行末尾补空单元格，所有行始终保持相同列数。

    模块名做成指令操作，点击即把 ``<前缀>help <模块名>`` 填入输入框。标签之所以能落在单元格
    中间，靠的正是适配器把指令操作及其后的文本一并并入上一项的行为（见
    ``bots/qqbot/context.py`` 的 ``inline_pending``）：整张表因此累积成一个文本块，
    竖线与换行均由此处显式写出。也正因如此，本函数产出的元素中**不得出现相邻的两个纯文本**
    —— 适配器只在指令操作之后才做合并，两个纯文本之间会被补上换行，表格随即被劈成两半。
    区隔行因此与上一组的收尾同处一个元素。

    :param msg: 消息会话。
    :param groups: (组名多语言键, 模块名列表) 的序列，模块名为空的组会被跳过。
    :param include_help_header: 是否在模块表格内加入 help 顶栏。
    :param permission: 顶栏权限类型，可选 ``user``、``admin`` 或 ``superuser``。
    :return: 消息元素列表；所有组皆空时返回空片段，空态文案由调用方负责。
    """
    locale = msg.session_info.locale
    prefix = msg.session_info.prefixes[0]
    groups = [(title_key, locale.t(title_key), names) for title_key, names in groups if names]
    if not groups:
        return []

    legend_keys = {
        "core.message.help.table.external": (
            "core.message.help.table.legend.external.enabled",
            "core.message.help.table.legend.external.disabled",
        ),
        "core.message.help.table.subscription": (
            "core.message.help.table.legend.subscription.enabled",
            "core.message.help.table.legend.subscription.disabled",
        ),
    }
    legends = {
        title_key: [locale.t(key) for key in legend_keys[title_key]]
        for title_key, _, names in groups
        if title_key in legend_keys and any(is_module_entry(item) for item in names)
    }
    columns = resolve_table_columns([len(names) for _, _, names in groups], separators=len(groups) - 1)
    if legends:
        columns = max(columns, 3)
    if include_help_header:
        columns = max(columns, 4)

    def group_header(title_key: str, title: str) -> str:
        cells = [escape_table_cell(title)]
        if title_key in legends:
            cells.extend(escape_table_cell(legend) for legend in legends[title_key])
        cells.extend([""] * (columns - len(cells)))
        return "|" + "".join(f" {cell} |" if cell else " |" for cell in cells) + "\n"

    parts = []
    # 表头与分隔线开头，随后各行的收尾、下一组的区隔行都并进同一个纯文本，
    # 以免相邻纯文本之间被适配器补上换行
    if include_help_header:
        bot_name = escape_table_cell(msg.session_info.bot_name or locale.t("bot_name"))
        language = escape_table_cell(locale.t("language"))
        version = get_version_display()
        version_text = (
            I18NContext("core.message.help.header.version", version=version)
            if version
            else I18NContext("core.message.help.header.version.unknown")
        )
        permission_text = locale.t(f"core.message.help.header.permission.{permission}")
        header_blanks = " |" * (columns - 4)
        parts.extend(
            [
                Plain(f"| {bot_name} | ", disable_joke=True),
                ActionText(
                    f"{prefix}locale",
                    show=I18NContext("core.message.help.header.locale", language=language),
                ),
                Plain(" | ", disable_joke=True),
                ActionText(f"{prefix}version", show=version_text),
            ]
        )
        pending = (
            f" | {escape_table_cell(permission_text)} |{header_blanks}\n"
            f"|{'---|' * columns}\n"
            f"{group_header(groups[0][0], groups[0][1])}"
        )
    else:
        pending = f"{group_header(groups[0][0], groups[0][1])}|{'---|' * columns}\n"

    for index, (title_key, title, names) in enumerate(groups):
        if index:
            pending += group_header(title_key, title)
        for offset, item in enumerate(names):
            parts.append(Plain(pending + "| " if not offset or offset % columns == 0 else pending, disable_joke=True))
            if is_module_entry(item):
                emoji, command = get_module_toggle(item, prefix)
                parts.append(ActionText(command, show=emoji))
                parts.append(Plain(" ~~" if item.unsupported else " ", disable_joke=True))
                parts.append(ActionText(f"{prefix}help {item.name}", show=item.name))
                cell_end = "~~" if item.unsupported else ""
            else:
                parts.append(ActionText(f"{prefix}help {item}", show=item))
                cell_end = ""
            if offset + 1 == len(names):
                padding = (columns - (offset + 1) % columns) % columns
                pending = cell_end + " |" * (padding + 1) + "\n"
            elif (offset + 1) % columns == 0:
                pending = cell_end + " |\n"
            else:
                pending = cell_end + " | "

    parts.append(Plain(pending, disable_joke=True))
    return parts


def strip_command_arguments(command: str) -> str:
    """
    去掉命令模板中的参数占位符，留下可以直接发出的命令主体。

    模板中的参数有四种形态：``<必需>``、``[可选]``、``[-选项]`` 与变长的 ``...``，
    其中可选项还会嵌套（如 ``~wiki <pagename> [-l <lang>]``、``~locale [<lang>]``），
    故按括号深度逐字符剔除，而非用正则逐个匹配 —— 后者遇到嵌套会留下孤立的方括号。

    原本带参数的命令保留一个尾随空格，点击填入后光标即落在参数位置，与既有的
    ``ActionText(f"{prefix}locale ")`` 一类写法一致；不带参数的命令则原样返回，
    点击后可直接发出。

    :param command: 命令模板，如 ``~wiki <pagename> [-l <lang>]``。
    :return: 去掉参数后的命令主体，如 ``~wiki ``。
    """
    kept = []
    depth = 0
    for char in command:
        if char in "<[":
            depth += 1
        elif char in ">]":
            depth = max(0, depth - 1)
        elif depth == 0:
            kept.append(char)
    body = " ".join(word for word in "".join(kept).split() if word != "...")
    return f"{body} " if body != command.strip() else body


def build_command_table(msg: Bot.MessageSession, help_doc: dict, regex_rows: list[tuple[str, str]]) -> list:
    """
    把一个模块的命令、选项与正则排成一张 markdown 表。

    与模块表格同一思路：高度封顶，条目变多时由列数吸收 —— 只是这里的一「列」是「命令 + 说明」
    一对，故实际列数为对数的两倍。命令多的模块（如 maimai 有 22 条）因此从二十余行压到十行以内。

    命令、选项、正则同处一张表，后两者各以一行区隔行引出。命令做成指令操作，展示的是完整模板，
    填入输入框的却是去掉参数占位符后的主体 —— 占位符照原样填进去还得用户自行删掉，反倒碍事。
    选项与正则不做成指令操作：前者不能单独成命令，后者本就不是命令。

    与 :func:`build_module_table` 同理，产出的元素中不得出现相邻的两个纯文本，故区隔行与
    上一行的收尾同处一个元素。

    :param msg: 消息会话。
    :param help_doc: :meth:`CommandParser.return_json_help_doc` 的产出。
    :param regex_rows: (正则表达式, 说明) 序列。
    :return: 消息元素列表；无任何内容时返回空片段。
    """
    locale = msg.session_info.locale
    args = help_doc.get("args") or []
    options = help_doc.get("options") or []

    # 每节为 (区隔行文案, [(种类, 首列, 次列), ...])；命令一节不带区隔行。
    # 种类决定首列如何落到单元格里：command 做成指令操作，code 已是成型的行内代码，
    # text 则照常转义。
    sections = []
    if args:
        sections.append((None, [("command", item["args"], item.get("desc") or "") for item in args]))
    if options:
        rows = [("text", flag, desc) for option in options for flag, desc in option.items()]
        sections.append((locale.t("core.message.help.table.options"), rows))
    if regex_rows:
        # 正则满是格式标记字符，包进行内代码原样呈现，不再逐字符转义
        rows = [("code", format_table_code(pattern), desc) for pattern, desc in regex_rows]
        sections.append((locale.t("core.message.help.table.regex"), rows))
    if not sections:
        return []

    separators = sum(1 for title, _ in sections if title)
    pairs = resolve_table_columns([len(rows) for _, rows in sections], separators=separators, minimum=1)
    columns = pairs * 2
    blanks = " |" * (columns - 1)
    command_title = escape_table_cell(locale.t("core.message.help.table.command"))
    desc_title = escape_table_cell(locale.t("core.message.help.table.desc"))

    parts = []
    pending = "|" + f" {command_title} | {desc_title} |" * pairs + f"\n|{'---|' * columns}\n"

    for title, rows in sections:
        if title:
            pending += f"| {escape_table_cell(title)} |{blanks}\n"
        for start in range(0, len(rows), pairs):
            # 末行补空的成对单元格，markdown 要求各行的列数一致
            chunk = rows[start : start + pairs]
            chunk += [("text", "", "")] * (pairs - len(chunk))
            pending += "| "
            for kind, first, second in chunk:
                if kind == "command":
                    parts.append(Plain(pending, disable_joke=True))
                    parts.append(ActionText(strip_command_arguments(first), show=escape_table_cell(first)))
                    pending = f" | {escape_table_cell(second)} | "
                else:
                    # code 已由 format_table_code() 处理妥当，再转义会把围栏内的反斜杠显示出来
                    cell = first if kind == "code" else escape_table_cell(first)
                    pending += f"{cell} | {escape_table_cell(second)} | "
            pending = pending.rstrip() + "\n"
    # 末尾保留换行，理由同 build_module_table()：表格靠空行终结
    parts.append(Plain(pending, disable_joke=True))
    return parts


def get_help_link_buttons(msg: Bot.MessageSession, include_modules: bool = True) -> list[tuple[str, str]]:
    """
    构造帮助菜单底部的三个入口按钮：模块列表、在线文档、关于我们。

    模块列表与关于我们使用命令回流，在线文档使用平台原生链接跳转。

    按钮命令一律使用 command_prefix：按钮回流经 interaction 事件另建会话，其可用前缀
    取自全局配置，不含各平台在常规消息入口所用的前缀。

    :param msg: 消息会话。
    :return: （标签, 命令）序列；会话不具备按钮能力时为空列表。
    """
    if not msg.session_info.support_button:
        return []
    locale = msg.session_info.locale
    prefix = command_prefix[0]
    buttons = []
    if include_modules:
        buttons.append((locale.t("core.message.help.button.modules"), f"{prefix}module list"))
    if help_url:
        buttons.append(
            (
                locale.t("core.message.help.button.document"),
                help_url,
            )
        )
    buttons.append((locale.t("core.message.help.button.about"), f"{prefix}about"))
    return buttons


def get_setup_button_data(msg: Bot.MessageSession) -> list[ButtonRows]:
    """
    构造帮助菜单底部直达设置面板的按钮。

    按钮点击后经 interaction 事件另行建立会话，该会话的可用前缀取自全局配置，
    并不包含各平台在常规消息入口所用的前缀，故此处须使用 command_prefix。

    文案取自面板专设的按钮键，而非面板标题：后者带有分隔用的方括号，套进按钮里并不好看。

    :param msg: 消息会话。
    :return: 按钮数据；会话不具备按钮能力时为空列表。
    """
    if not msg.session_info.support_button:
        return []
    locale = msg.session_info.locale
    return arrange_buttons(
        [
            (locale.t("core.message.setup.list.button.target"), f"{command_prefix[0]}setup list target"),
            (locale.t("core.message.setup.list.button.sender"), f"{command_prefix[0]}setup list sender"),
        ]
    )


def get_help_button_data(msg: Bot.MessageSession, include_modules: bool = True) -> list[ButtonRows]:
    """
    构造帮助菜单底部的全部按钮：设置面板一行，三个入口按钮另起一行。

    两组各自排布再拼接，而非合并后交由 arrange_buttons 均分——后者会把五个按钮摊成
    三、二两行，把入口按钮拆散。

    :param msg: 消息会话。
    :return: 按钮数据；会话不具备按钮能力时为空列表。
    """
    return get_setup_button_data(msg) + arrange_buttons(get_help_link_buttons(msg, include_modules), per_row=3)


def get_module_list_button_data(msg: Bot.MessageSession) -> list[ButtonRows]:
    """构造模块列表底部的在线文档按钮。"""
    if not msg.session_info.support_button or not help_url:
        return []
    return arrange_buttons(
        [(msg.session_info.locale.t("core.message.help.button.document"), f"{command_prefix[0]}help --doc")]
    )


def append_qqbot_permissions_prompt(msg: Bot.MessageSession, help_msg: MessageChain) -> None:
    if not qqbot_permissions_limited(msg):
        return
    help_msg.append(
        I18NContext(
            "core.message.help.qqbot.permissions.prompt",
            cmd=ActionText(
                f"{msg.session_info.prefixes[0]}help permissions",
                show=I18NContext("core.message.help.qqbot.permissions.action"),
            ),
        )
    )


@hlp.command(
    "permissions {{I18N:core.help.help.permissions}}",
    available_for="QQBot",
    priority=2,
)
async def qqbot_permissions(msg: Bot.MessageSession):
    await msg.finish(I18NContext("core.message.help.qqbot.permissions"))


@hlp.command(
    "<module> [--legacy] [--image] {{I18N:core.help.help.detail}}",
    options_desc={
        "--legacy": "{I18N:help.option.legacy}",
        "--image": "{I18N:help.option.image}",
    },
)
async def _(msg: Bot.MessageSession, module: str):
    is_base_superuser = msg.session_info.sender_id in Bot.base_superuser_list
    is_superuser = msg.check_super_user()
    module_list = ModulesManager.return_modules_list(
        target_from=msg.session_info.target_from, client_name=msg.session_info.client_name
    )
    alias = ModulesManager.modules_aliases
    force_image = msg.parsed_msg.get("--image", False)
    force_legacy = msg.parsed_msg.get("--legacy", False) and not force_image

    if msg.parsed_msg:
        mdocs = []
        malias = []
        # 表格版另需成对的（正则, 说明），与拼成一行的 mdocs 并行收集
        regex_rows = []

        help_name = alias[module].split()[0] if module in alias else module.split()[0]
        if help_name in module_list:
            module_ = module_list[help_name]

            if not module_._db_load:
                await msg.finish(I18NContext("parser.module.unloaded", module=help_name))
            if module_.desc:
                desc = msg.session_info.locale.t_str(module_.desc)
                mdocs.append(desc)

            help_ = CommandParser(
                module_,
                msg=msg,
                module_name=module_.module_name,
                command_prefixes=msg.session_info.prefixes,
                is_superuser=is_superuser,
            )

            if help_.args:
                mdocs.append(help_.return_formatted_help_doc())

            regex_list = module_.regex_list.get(
                msg.session_info.target_from,
                show_required_superuser=is_superuser,
                show_required_base_superuser=is_base_superuser,
            )
            regex_disable_prefixes = get_regex_disable_prefix_display()

            devs_msg = ""
            if (module_.required_superuser and not is_superuser) or (
                module_.required_base_superuser and not is_base_superuser
            ):
                pass
            elif module_.unsupported_reason(msg.session_info):
                pass
            else:
                if regex_list:
                    mdocs.append(str(I18NContext("core.help.regex.note")))
                    for regex in regex_list:
                        pattern = None
                        if isinstance(regex.pattern, str):
                            pattern = regex.pattern
                        elif isinstance(regex.pattern, re.Pattern):
                            pattern = regex.pattern.pattern
                        if pattern:
                            # 表格版把正则包进行内代码，不需要也不能要这层反斜杠转义，
                            # 故在转义前先留一份原样的
                            raw_pattern = pattern
                            if msg.session_info.support_markdown:
                                pattern = re.sub(r"([\\`*_{}\[\]()#+\-.!>~|])", r"\\\1", pattern)
                            rdesc = regex.desc
                            if rdesc:
                                rdesc = msg.session_info.locale.t_str(rdesc)
                                mdocs.append(
                                    f"{pattern}{str(I18NContext('core.message.help.regex.detail', msg=rdesc))}"
                                )
                            else:
                                mdocs.append(f"{pattern}{str(I18NContext('core.message.help.regex.no_information'))}")
                            regex_rows.append((raw_pattern, rdesc or ""))
                    if regex_disable_prefixes:
                        mdocs.append(I18NContext("core.help.regex.disable_tip", prefixes=regex_disable_prefixes))

                if module_.alias:
                    for a in module_.alias:
                        malias.append(f"{a} -> {module_.alias[a]}")
                if module_.developers and not module_.base:
                    devs_msg = str(I18NContext("core.help.author")) + "{I18N:message.delimiter}".join(
                        module_.developers
                    )
                else:
                    devs_msg = ""

            if module_.doc:
                if help_page_url := CoreConfig.help_page_url:
                    wiki_msg = I18NContext(
                        "core.message.help.helpdoc.address",
                        url=MessageChain.assign(Url(help_page_url.replace("${module}", help_name), trusted=True)),
                    )

                elif help_url:
                    wiki_msg = I18NContext(
                        "core.message.help.helpdoc.address",
                        url=MessageChain.assign(Url(help_url + help_name, trusted=True)),
                    )

                else:
                    wiki_msg = ""
            else:
                wiki_msg = ""

            # 表格版优先于图片版：命令可点击填入，且与模块列表的排法一致
            if should_use_markdown_table(msg, force_image, force_legacy):
                table = build_command_table(msg, help_.return_json_help_doc(), regex_rows)
                if table:
                    detail = [
                        Plain(
                            get_module_type_display(module_, msg.session_info.locale) + "\n",
                            disable_joke=True,
                        )
                    ]
                    if module_.desc:
                        detail.append(Plain(msg.session_info.locale.t_str(module_.desc) + "\n", disable_joke=True))
                    detail += table
                    if regex_rows and regex_disable_prefixes:
                        detail.append(I18NContext("core.help.regex.disable_tip", prefixes=regex_disable_prefixes))
                    if devs_msg:
                        detail.append(Plain(devs_msg))
                    if wiki_msg:
                        detail.append(wiki_msg)
                    # 纯正则模块的表格里没有可点击命令，整条消息全是纯文本，
                    # 不显式声明会被平台退回纯文本，表格标记原样露出
                    await msg.finish(detail, force_markdown=True)

            if not force_legacy and msg.session_info.support_image and Bot.Info.web_render_status:
                if (module_.required_superuser and not is_superuser) or (
                    module_.required_base_superuser and not is_base_superuser
                ):
                    pass
                elif module_.unsupported_reason(msg.session_info):
                    pass
                elif any(
                    (module_.alias, module_.desc, module_.developers, help_.return_formatted_help_doc(), regex_list)
                ):
                    try:
                        html_content = await env.get_template("help_doc.html").render_async(
                            locale=msg.session_info.locale,
                            module=module_,
                            help=help_,
                            help_name=help_name,
                            regex_list=regex_list,
                            escape=escape,
                            isinstance=isinstance,
                            str=str,
                            repattern=re.Pattern,
                            regex_disable_prefixes=regex_disable_prefixes,
                            use_font_mirror=use_font_mirror,
                        )

                        # fname = f"{random_cache_path()}.html"
                        # with open(fname, "w", encoding="utf-8") as fi:
                        #     fi.write(html_content)

                        images = await web_render.element_screenshot(
                            ElementScreenshotOptions(content=html_content, element=[".botbox"])
                        )

                        cb: list[ImageElement] = cb64imglst(images, bot_img=True)

                        msgchain = MessageChain.assign(cb)
                        if wiki_msg:
                            msgchain.append(wiki_msg)
                        await msg.finish(msgchain)
                    except Exception:
                        Logger.exception()

                if wiki_msg:
                    await msg.finish(wiki_msg)
                else:
                    await msg.finish(I18NContext("core.help.info.none"))

            doc_msg = mdocs + [devs_msg, wiki_msg]
            if doc_msg:
                await msg.finish(doc_msg)
            else:
                await msg.finish(I18NContext("core.help.info.none"))
        else:
            await msg.finish(I18NContext("core.message.help.not_found"))


@hlp.command(
    "[--legacy] [--doc] [--image] [--donate] {{I18N:core.help.help}}",
    options_desc={
        "--legacy": "{I18N:help.option.legacy}",
        "--doc": "{I18N:core.help.option.doc}",
        "--image": "{I18N:help.option.image}",
        "--donate": "{I18N:core.help.option.donate}",
    },
)
async def help_overview(msg: Bot.MessageSession):
    # 支持 Markdown 表格的平台优先排成宽表；其余平台保留图片帮助，图片生成失败后
    # 再降级到可点击列表或纯文本。显式要求 --legacy 者始终得到最朴素的版本。
    if msg.parsed_msg and msg.parsed_msg.get("--doc", False) and bool(help_url):
        await msg.finish(
            I18NContext("core.message.help.document", url=MessageChain.assign(Url(help_url, trusted=True)))
        )
    if msg.parsed_msg and msg.parsed_msg.get("--donate", False) and bool(donate_url):
        await msg.finish(
            I18NContext("core.message.help.donate", url=MessageChain.assign(Url(donate_url, trusted=True)))
        )
    parsed_msg = msg.parsed_msg or {}
    force_image = parsed_msg.get("--image", False)
    force_legacy = parsed_msg.get("--legacy", False) and not force_image
    use_table = should_use_markdown_table(msg, force_image, force_legacy)
    use_clickable = not use_table and not force_legacy and msg.session_info.support_action_text
    qqbot_admin = msg.session_info.client_name == "QQBot" and await msg.check_permission()
    show_all_modules = qqbot_admin and not force_legacy

    legacy_help = True
    if not use_table and not force_legacy and msg.session_info.support_image:
        imgs = await help_generator(msg, show_disabled_modules=show_all_modules)
        if imgs:
            legacy_help = False

            help_msg_list = MessageChain.assign(
                I18NContext(
                    "core.message.help.detail",
                    prefix=msg.session_info.prefixes[0],
                    cmd=ActionText(f"{msg.session_info.prefixes[0]}help "),
                )
            )
            if not show_all_modules:
                help_msg_list.append(
                    I18NContext(
                        "core.message.help.all_modules",
                        prefix=msg.session_info.prefixes[0],
                        cmd=ActionText(f"{msg.session_info.prefixes[0]}module list"),
                    )
                )
            if help_url:
                help_msg_list.append(
                    I18NContext("core.message.help.document", url=MessageChain.assign(Url(help_url, trusted=True)))
                )
            if donate_url:
                help_msg_list.append(
                    I18NContext("core.message.help.donate", url=MessageChain.assign(Url(donate_url, trusted=True)))
                )
            help_msg_list.append(
                ButtonFrame(get_setup_button_data(msg) if show_all_modules else get_help_button_data(msg))
            )
            await msg.finish(imgs + help_msg_list)
    if legacy_help:
        is_base_superuser = msg.session_info.sender_id in Bot.base_superuser_list
        is_superuser = msg.check_super_user()
        module_list = ModulesManager.return_modules_list(
            target_from=msg.session_info.target_from, client_name=msg.session_info.client_name
        )
        target_enabled_list = msg.session_info.enabled_modules or []

        essential = []
        module_ = []

        for key, value in module_list.items():
            if key[0] == "_":
                continue
            if not value._db_load and not value.base:
                continue
            if value.hidden:
                continue
            if value.unsupported_reason(msg.session_info) and not show_all_modules:
                continue
            if not is_superuser and value.required_superuser or not is_base_superuser and value.required_base_superuser:
                continue

            if value.base:
                essential.append(key)
            else:
                module_.append(key)
        if not show_all_modules:
            module_ = [m for m in module_ if m in target_enabled_list]
        module_, subscription = split_subscription_modules(module_list, module_)
        if show_all_modules:
            module_ = [
                create_module_entry(module_list[name], name, target_enabled_list, msg.session_info) for name in module_
            ]
            subscription = [
                create_module_entry(module_list[name], name, target_enabled_list, msg.session_info)
                for name in subscription
            ]

        if use_table:
            # 各类模块同处一张表，以一行区隔行分开；表格以纯文本收尾，无须 end_inline_run()
            help_msg = MessageChain.assign(
                build_module_table(
                    msg,
                    [
                        ("core.message.help.table.base", essential),
                        ("core.message.help.table.external", module_),
                        ("core.message.help.table.subscription", subscription),
                    ],
                    include_help_header=True,
                    permission="superuser" if is_superuser else "admin" if qqbot_admin else "user",
                )
            )
            help_msg += I18NContext("core.message.help.mdtable")
            if has_unsupported_entries(
                [
                    ("core.message.help.table.base", essential),
                    ("core.message.help.table.external", module_),
                    ("core.message.help.table.subscription", subscription),
                ]
            ):
                append_qqbot_permissions_prompt(msg, help_msg)
            help_msg.append(ButtonFrame(get_help_button_data(msg, include_modules=not show_all_modules)))
            await msg.finish(help_msg, force_markdown=True)
        if use_clickable:
            help_msg = MessageChain.assign(
                build_clickable_modules(
                    msg,
                    [
                        ("core.message.help.legacy.base", essential),
                        ("core.message.help.legacy.external", module_),
                        ("core.message.help.legacy.subscription", subscription),
                    ],
                )
            )
            end_inline_run(help_msg)
        else:
            help_msg = MessageChain.assign([I18NContext("core.message.help.legacy.base")])
            help_msg.append(Plain(format_module_entries(essential), disable_joke=True))
            if module_:
                help_msg.append(I18NContext("core.message.help.legacy.external"))
                help_msg.append(Plain(format_module_entries(module_), disable_joke=True))
            if subscription:
                help_msg.append(I18NContext("core.message.help.legacy.subscription"))
                help_msg.append(Plain(format_module_entries(subscription), disable_joke=True))
        help_msg.append(
            I18NContext(
                "core.message.help.detail",
                prefix=msg.session_info.prefixes[0],
                cmd=ActionText(f"{msg.session_info.prefixes[0]}help "),
            )
        )
        if not show_all_modules:
            help_msg.append(
                I18NContext(
                    "core.message.help.all_modules",
                    prefix=msg.session_info.prefixes[0],
                    cmd=ActionText(f"{msg.session_info.prefixes[0]}module list"),
                )
            )
        if has_unsupported_entries(
            [
                ("core.message.help.legacy.base", essential),
                ("core.message.help.legacy.external", module_),
                ("core.message.help.legacy.subscription", subscription),
            ]
        ):
            append_qqbot_permissions_prompt(msg, help_msg)
        if help_url:
            help_msg.append(
                I18NContext("core.message.help.document", url=MessageChain.assign(Url(help_url, trusted=True)))
            )
        if donate_url:
            help_msg.append(
                I18NContext("core.message.help.donate", url=MessageChain.assign(Url(donate_url, trusted=True)))
            )
        help_msg.append(ButtonFrame(get_help_button_data(msg, include_modules=not show_all_modules)))
        await msg.finish(help_msg)


async def modules_list_help(msg: Bot.MessageSession, legacy, force_image=False):
    # 与 ~help 同理：表格不可用时优先保留图片，图片生成失败后再降级到文字版
    use_table = should_use_markdown_table(msg, force_image, legacy)
    use_clickable = not use_table and not legacy and msg.session_info.support_action_text

    legacy_help = True
    if not use_table and msg.session_info.support_image and not legacy:
        imgs = await help_generator(msg, show_disabled_modules=True, show_base_modules=False, show_dev_modules=False)
        if imgs:
            legacy_help = False
            help_msg = MessageChain.assign(
                I18NContext(
                    "core.message.help.detail",
                    prefix=msg.session_info.prefixes[0],
                    cmd=ActionText(f"{msg.session_info.prefixes[0]}help "),
                )
            )
            if help_url:
                help_msg.append(
                    I18NContext("core.message.help.document", url=MessageChain.assign(Url(help_url, trusted=True)))
                )
            help_msg.append(ButtonFrame(get_module_list_button_data(msg)))
            await msg.finish(imgs + help_msg)
    if legacy_help:
        can_manage_modules = msg.session_info.client_name == "QQBot" and await msg.check_permission()
        module_list = ModulesManager.return_modules_list(
            target_from=msg.session_info.target_from, client_name=msg.session_info.client_name
        )
        target_enabled_list = msg.session_info.enabled_modules or []
        module_ = []
        for x in module_list:
            if x[0] == "_":
                continue
            if (
                module_list[x].base
                or module_list[x].hidden
                or not module_list[x]._db_load
                or module_list[x].required_superuser
                or module_list[x].required_base_superuser
            ):
                continue
            module_.append(module_list[x].module_name)
        module_, subscription = split_subscription_modules(module_list, module_)
        if can_manage_modules:
            module_ = [
                create_module_entry(module_list[name], name, target_enabled_list, msg.session_info) for name in module_
            ]
            subscription = [
                create_module_entry(module_list[name], name, target_enabled_list, msg.session_info)
                for name in subscription
            ]
        if not module_ and not subscription:
            help_msg = MessageChain.assign(I18NContext("core.message.help.legacy.availables.none"))
        elif use_table:
            # 与 ~help 同款表格，收尾同样是纯文本
            help_msg = MessageChain.assign(
                build_module_table(
                    msg,
                    [
                        ("core.message.help.table.title", module_),
                        ("core.message.help.table.subscription", subscription),
                    ],
                )
            )
            help_msg += I18NContext("core.message.help.mdtable")
            append_qqbot_permissions_prompt(msg, help_msg)
            help_msg.append(ButtonFrame(get_module_list_button_data(msg)))
            await msg.finish(help_msg, force_markdown=True)
        elif use_clickable:
            help_msg = MessageChain.assign(
                build_clickable_modules(
                    msg,
                    [
                        ("core.message.help.legacy.availables", module_),
                        ("core.message.help.legacy.subscription", subscription),
                    ],
                )
            )
            end_inline_run(help_msg)
        else:
            help_msg = MessageChain.assign([])
            if module_:
                help_msg.append(I18NContext("core.message.help.legacy.availables"))
                help_msg.append(Plain(format_module_entries(module_), disable_joke=True))
            if subscription:
                help_msg.append(I18NContext("core.message.help.legacy.subscription"))
                help_msg.append(Plain(format_module_entries(subscription), disable_joke=True))
        help_msg.append(
            I18NContext(
                "core.message.help.detail",
                prefix=msg.session_info.prefixes[0],
                cmd=ActionText(f"{msg.session_info.prefixes[0]}help "),
            )
        )
        append_qqbot_permissions_prompt(msg, help_msg)
        if help_url:
            help_msg.append(
                I18NContext("core.message.help.document", url=MessageChain.assign(Url(help_url, trusted=True)))
            )
        help_msg.append(ButtonFrame(get_module_list_button_data(msg)))
        await msg.finish(help_msg)


async def help_generator(
    msg: Bot.MessageSession,
    show_base_modules: bool = True,
    show_disabled_modules: bool = False,
    show_dev_modules: bool = True,
):
    is_base_superuser = msg.session_info.sender_id in Bot.base_superuser_list
    is_superuser = msg.check_super_user()
    module_list = ModulesManager.return_modules_list(
        target_from=msg.session_info.target_from, client_name=msg.session_info.client_name
    )
    target_enabled_list = msg.session_info.enabled_modules

    dev_module_list = []
    essential = {}
    module_ = {}

    for key, value in module_list.items():
        if key[0] == "_":
            continue
        if not value._db_load and not value.base:
            continue
        if value.hidden:
            continue
        if value.unsupported_reason(msg.session_info):
            continue
        if not is_superuser and value.required_superuser or not is_base_superuser and value.required_base_superuser:
            continue

        if value.base:
            essential[key] = value
        else:
            module_[key] = value

        if value.required_superuser or value.required_base_superuser:
            dev_module_list.append(key)

    if not show_disabled_modules:
        module_ = {k: v for k, v in module_.items() if k in target_enabled_list or k in dev_module_list}

    if show_base_modules:
        module_list = {**essential, **module_}
    else:
        module_list = module_

    if not show_dev_modules:
        module_list = {k: v for k, v in module_.items() if k not in dev_module_list}

    module_groups = [
        ("core.message.help.table.base", "base", {k: v for k, v in module_list.items() if v.base}),
        (
            "core.message.help.table.external",
            "external",
            {k: v for k, v in module_list.items() if not v.base and not v.rss},
        ),
        (
            "core.message.help.table.subscription",
            "subscription",
            {k: v for k, v in module_list.items() if not v.base and v.rss},
        ),
    ]

    html_content = await env.get_template("module_list.html").render_async(
        msg=msg,
        locale=msg.session_info.locale,
        CommandParser=CommandParser,
        is_base_superuser=is_base_superuser,
        is_superuser=is_superuser,
        len=len,
        module_list=module_list,
        module_groups=module_groups,
        show_disabled_modules=show_disabled_modules,
        target_enabled_list=target_enabled_list,
        use_font_mirror=use_font_mirror,
    )
    fname = f"{random_cache_path()}.html"
    with open(fname, "w", encoding="utf-8") as fi:
        fi.write(html_content)

    images = await web_render.element_screenshot(ElementScreenshotOptions(content=html_content, element=[".botbox"]))
    if images:
        return cb64imglst(images, bot_img=True)
    return None
