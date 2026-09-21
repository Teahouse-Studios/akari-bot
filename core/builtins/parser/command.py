"""命令解析模块 - 解析和处理用户命令。"""

import re
import traceback
from typing import TYPE_CHECKING

from core.config.base import BaseConfig, CoreConfig
from core.constants.exceptions import InvalidCommandFormatError
from core.exports import exports
from core.i18n import Locale
from core.logger import Logger
from core.types import Module
from .args import parse_argv, Template, templates_to_str, ArgumentPattern, DescPattern

if TYPE_CHECKING:
    from core.builtins.bot import Bot

default_locale = BaseConfig.default_locale

_CN_QUOTE_PATTERN = re.compile(r"[“”]")

_QUOTE_CHARS = ('"', "'")


def _split_command(command: str) -> list[str]:
    split_command = []
    index = 0
    length = len(command)
    while index < length:
        if command[index].isspace():
            index += 1
            continue

        quote = command[index]
        if quote in _QUOTE_CHARS:
            end = command.find(quote, index + 1)
            if end != -1 and (end + 1 == length or command[end + 1].isspace()):
                split_command.append(command[index + 1 : end])
                index = end + 1
                continue

        # 例外：引号紧跟在选项内联值的 `=` 之后时作为分组符号（如 --lang="zh cn"）
        token = []
        end = index
        while end < length and not command[end].isspace():
            char = command[end]
            if char in _QUOTE_CHARS and end > index and command[end - 1] == "=" and command[index] == "-":
                quote_end = command.find(char, end + 1)
                if quote_end != -1 and (quote_end + 1 == length or command[quote_end + 1].isspace()):
                    token.append(command[index:end])
                    token.append(command[end + 1 : quote_end])
                    index = quote_end + 1
                    break
            end += 1
        else:
            token.append(command[index:end])
            index = end

        split_command.append("".join(token))

    return split_command


class CommandParser:
    """命令解析器 - 用于解析和验证用户输入的命令。"""

    def __init__(
        self,
        args: Module,
        command_prefixes: list,
        module_name=None,
        msg: "Bot.MessageSession | None" = None,
        is_superuser: bool | None = None,
        is_admin: bool | None = None,
    ):
        """
        初始化命令解析器。

        :param args: 模块对象，包含命令定义
        :param command_prefixes: 命令前缀列表
        :param module_name: 模块名称
        :param msg: 消息会话对象（用于权限检查）
        :param is_superuser: 是否为超级用户（如为 None 则从会话自动检测）
        :param is_admin: 是否为场景管理员。为 None 时不过滤管理员命令，保持命令解析行为；
            传入布尔值则据其过滤 ``required_admin`` 命令，供帮助文档按权限展示
        """
        self.command_prefixes = command_prefixes

        self.module_name = module_name

        # 存储原始模块模板定义（只读使用，无需拷贝）
        self.origin_template = args

        self.msg: "Bot.MessageSession | None" = msg

        self.options_desc = {}

        self.lang = self.msg.session_info.locale if self.msg else Locale(default_locale)

        command_templates = {}

        if is_superuser is None:
            is_superuser = self.msg.check_super_user() if self.msg else False

        is_base_superuser = (
            (self.msg.session_info.sender_id in exports["Bot"].base_superuser_list) if self.msg else False
        )

        for match in (
            args.command_list.set
            if not self.msg
            else args.command_list.get(
                self.msg.session_info.target_from,
                show_required_superuser=is_superuser,
                show_required_base_superuser=is_base_superuser,
                show_required_admin=True if is_admin is None else (is_admin or is_superuser),
            )
        ):
            if match.command_template:
                for m in match.command_template:
                    command_templates[m] = {"priority": match.priority, "meta": match}
                    if not any(isinstance(arg, ArgumentPattern) for arg in m.args) and not command_templates.get(
                        "", False
                    ):
                        command_templates[""] = {"priority": match.priority, "meta": match}
            else:
                command_templates[""] = {"priority": match.priority, "meta": match}

            if match.options_desc:
                for m in match.options_desc:
                    self.options_desc[m] = match.options_desc[m]

        self.args: dict[Template, dict] = command_templates

        seen_values = set()
        deduped_options_desc = {}
        for k, v in self.options_desc.items():
            if v not in seen_values:
                deduped_options_desc[k] = v
                seen_values.add(v)
        self.options_desc = deduped_options_desc

        # 预计算过滤后的 args 列表（排除空字符串占位符），避免每次 parse 重建
        self._filtered_args = [a for a in self.args if a != ""]

    def return_formatted_help_doc(self, locale=None) -> str:
        """生成格式化的帮助文档字符串。"""

        if not self.args:
            return ""

        if locale:
            locale = Locale(locale)
        else:
            locale = self.lang

        format_args = templates_to_str(self._filtered_args, with_desc=True)

        args_lst = []
        if not format_args and "" in self.args and not self.origin_template.doc:
            args_lst.append(f"{self.command_prefixes[0]}{self.module_name}")
        for x in format_args:
            x = locale.t_str(x, locale_failed_prompt=False)
            x = f"{self.command_prefixes[0]}{self.module_name} {x}"
            args_lst.append(x)
        args = "\n".join(y for y in args_lst)

        if self.options_desc:
            options_desc_fmtted = []
            for m, desc in self.options_desc.items():
                desc = locale.t_str(desc, locale_failed_prompt=False)
                options_desc_fmtted.append(f"{m} - {desc}")
            args += f"\n{locale.t('core.help.options')}\n" + "\n".join(options_desc_fmtted)
        return args

    def return_json_help_doc(self, locale=None) -> dict:
        """生成 JSON 格式的帮助文档。

        :param locale: 地区/语言代码。如为 None，使用会话默认地区
        :return: 包含 args 和 options 的字典
        """
        if not self.args:
            return {}

        if locale:
            locale = Locale(locale)
        else:
            locale = self.lang

        format_args = templates_to_str(self._filtered_args, with_desc=True)

        args_list = []

        if not format_args and "" in self.args and not self.origin_template.doc:
            args_list.append({"args": f"{self.command_prefixes[0]}{self.module_name}", "desc": ""})

        for x in format_args:
            desc = ""

            match = re.fullmatch(r"- (\{I18N:.*?\})", x)
            if match:
                x = ""
                desc = locale.t_str(match.group(1), locale_failed_prompt=False)
            else:
                match = re.search(r" - (\{I18N:.*?\})$", x)
                if match:
                    x = x[: match.start()]
                    desc = locale.t_str(match.group(1), locale_failed_prompt=False)

            args_list.append({"args": f"{self.command_prefixes[0]}{self.module_name} {x}", "desc": desc})

        options_desc_fmtted = []
        if self.options_desc:
            for m, desc in self.options_desc.items():
                desc = locale.t_str(desc, locale_failed_prompt=False)
                options_desc_fmtted.append({m: desc})

        return {"args": args_list, "options": options_desc_fmtted}

    def parse(self, command):
        """解析用户输入的命令字符串。

        :param command: 用户输入的完整命令字符串（不包括前缀）
        :return: (CommandMeta, 参数字典) 元组
                 - CommandMeta: 匹配的命令元数据
                 - 参数字典: 解析后的参数，如果无参数则为 None
        :raises InvalidCommandFormatError: 如果命令格式不正确或无法匹配任何模板
        """
        if not self.args:
            return None

        # 替换中文引号为英文引号（兼容中文输入法）
        command = _CN_QUOTE_PATTERN.sub('"', command)

        # 按空白符号分割命令，支持引号分组，并原样保留引号、反斜杠等字面字符
        split_command = _split_command(command)

        Logger.trace("splited command: " + str(split_command))

        try:
            if not self.origin_template.command_list.set:
                if len(split_command) == 1:
                    return None, None
            else:
                if len(split_command) == 1:
                    if "" in self.args:
                        return self.args[""]["meta"], None

                    for arg in self.args:
                        if len(arg.args) == 1 and isinstance(arg.args[0], DescPattern):
                            return self.args[arg]["meta"], None

                    raise InvalidCommandFormatError

                # split_command[1:] 是除去命令名之外的所有参数
                base_match = parse_argv(split_command[1:], self._filtered_args)

                return (
                    self.args[base_match.original_template]["meta"],
                    base_match.args,
                )

        except InvalidCommandFormatError:
            if CoreConfig.debug:
                traceback.print_exc()
            raise InvalidCommandFormatError
