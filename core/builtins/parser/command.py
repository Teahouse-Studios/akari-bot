import copy
import re
import shlex
import traceback
from typing import Dict, Optional, Union, TYPE_CHECKING

from ...exports import exports

if TYPE_CHECKING:
    from core.builtins.bot import Bot

from core.config import Config
from core.constants.exceptions import InvalidCommandFormatError
from core.i18n import Locale
from core.logger import Logger
from core.types import Module
from .args import parse_argv, Template, templates_to_str, DescPattern

default_locale = Config("default_locale", cfg_type=str)


class CommandParser:
    def __init__(
        self,
        args: Module,
        command_prefixes: list,
        module_name=None,
        msg: Optional["Bot.MessageSession"] = None,
        is_superuser: Optional[bool] = None,
    ):
        args = copy.deepcopy(args)
        self.command_prefixes = command_prefixes
        self.module_name = module_name
        self.origin_template = args
        self.msg: Union["Bot.MessageSession", None] = msg
        self.options_desc = {}
        self.lang = self.msg.session_info.locale if self.msg else Locale(default_locale)
        help_docs = {}
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
            )
        ):
            if match.help_doc:
                for m in match.help_doc:
                    help_docs[m] = {"priority": match.priority, "meta": match}
            else:
                help_docs[""] = {"priority": match.priority, "meta": match}
            if match.options_desc:
                for m in match.options_desc:
                    self.options_desc[m] = match.options_desc[m]

        self.args: Dict[Union[Template, ""], dict] = help_docs

        seen_values = set()
        deduped_options_desc = {}
        for k, v in self.options_desc.items():
            if v not in seen_values:
                deduped_options_desc[k] = v
                seen_values.add(v)
        self.options_desc = deduped_options_desc

    def return_formatted_help_doc(self, locale=None) -> str:
        if not self.args:
            return ""

        if locale:
            locale = Locale(locale)
        else:
            locale = self.lang

        format_args = templates_to_str(
            [args for args in self.args if args != ""], with_desc=True
        )

        args_lst = []
        for x in format_args:
            x = locale.t_str(x, fallback_failed_prompt=False)
            x = f"{self.command_prefixes[0]}{self.module_name} {x}"
            args_lst.append(x)
        args = "\n".join(y for y in args_lst)

        if self.options_desc:
            options_desc_fmtted = []
            for m, desc in self.options_desc.items():
                desc = locale.t_str(desc, fallback_failed_prompt=False)
                options_desc_fmtted.append(f"{m} - {desc}")
            args += f"\n{locale.t("core.help.options")}\n" + "\n".join(
                options_desc_fmtted
            )
        return args

    def return_json_help_doc(self, locale=None) -> dict:
        if not self.args:
            return {}

        if locale:
            locale = Locale(locale)
        else:
            locale = self.lang

        format_args = templates_to_str(
            [args for args in self.args if args != ""], with_desc=True
        )

        args_list = []

        for x in format_args:
            desc = ""

            match = re.fullmatch(r"- (\{I18N:.*?\})", x)
            if match:
                x = ""
                desc = locale.t_str(match.group(1), fallback_failed_prompt=False)
            else:
                match = re.search(r" - (\{I18N:.*?\})$", x)
                if match:
                    x = x[:match.start()]
                    desc = locale.t_str(match.group(1), fallback_failed_prompt=False)

            args_list.append({
                "args": f"{self.command_prefixes[0]}{self.module_name} {x}",
                "desc": desc
            })

        options_desc_fmtted = []
        if self.options_desc:
            for m, desc in self.options_desc.items():
                desc = locale.t_str(desc, fallback_failed_prompt=False)
                options_desc_fmtted.append({m: desc})

        return {
            "args": args_list,
            "options": options_desc_fmtted
        }

    def parse(self, command):
        if not self.args:
            return None
        command = re.sub(r"[“”]", "\"", command)
        try:
            split_command = shlex.split(command)
        except ValueError:
            split_command = command.split(" ")
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
                base_match = parse_argv(
                    split_command[1:], [args for args in self.args if args != ""]
                )
                return (
                    self.args[base_match.original_template]["meta"],
                    base_match.args,
                )

        except InvalidCommandFormatError:
            traceback.print_exc()
            raise InvalidCommandFormatError
