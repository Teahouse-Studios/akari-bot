import copy
import re
import shlex
import traceback
from typing import Dict, Optional, Union

from core.builtins import base_superuser_list, MessageSession
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
        bind_prefix=None,
        msg: Optional[MessageSession] = None,
        is_superuser: Optional[bool] = None,
    ):
        args = copy.deepcopy(args)
        self.command_prefixes = command_prefixes
        self.bind_prefix = bind_prefix
        self.origin_template = args
        self.msg: Union[MessageSession, None] = msg
        self.options_desc = []
        self.lang = self.msg.locale if self.msg else Locale(default_locale)
        help_docs = {}
        if is_superuser is None:
            is_superuser = self.msg.check_super_user() if self.msg else False
        is_base_superuser = (
            (self.msg.target.sender_id in base_superuser_list) if self.msg else False
        )
        for match in (
            args.command_list.set
            if not self.msg
            else args.command_list.get(
                self.msg.target.target_from,
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
                    desc = self.lang.t_str(
                        match.options_desc[m], fallback_failed_prompt=False
                    )
                    self.options_desc.append(f"{m} - {desc}")
        self.args: Dict[Union[Template, ""], dict] = help_docs

    def return_formatted_help_doc(self) -> str:
        if not self.args:
            return ""
        lst = []
        format_args = templates_to_str(
            [args for args in self.args if args != ""], with_desc=True
        )
        for x in format_args:
            x = self.lang.t_str(x, fallback_failed_prompt=False)
            x = f"{self.command_prefixes[0]}{self.bind_prefix} {x}"
            lst.append(x)
        args = "\n".join(y for y in lst)
        if self.options_desc:
            options_desc = self.options_desc.copy()
            options_desc_localed = []
            for x in options_desc:
                x = self.lang.t_str(x, fallback_failed_prompt=False)
                options_desc_localed.append(x)
            options_desc_localed = list(set(options_desc_localed))  # 移除重复内容
            args += f"\n{self.lang.t("core.help.options")}\n" + "\n".join(
                options_desc_localed
            )
        return args

    def parse(self, command):
        if not self.args:
            return None
        command = re.sub(r"[“”]", "\"", command)
        try:
            split_command = shlex.split(command)
        except ValueError:
            split_command = command.split(" ")
        Logger.debug(split_command)
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
