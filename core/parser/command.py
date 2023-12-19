import copy
import re
import shlex
import traceback
from typing import Union, Dict

from core.exceptions import InvalidCommandFormatError
from core.types import MessageSession, Module
from core.utils.i18n import Locale, default_locale
from .args import parse_argv, Template, templates_to_str, DescPattern
from ..logger import Logger


class CommandParser:
    def __init__(self, args: Module, command_prefixes: list,
                 bind_prefix=None,
                 msg: MessageSession = None):
        args = copy.deepcopy(args)
        self.command_prefixes = command_prefixes
        self.bind_prefix = bind_prefix
        self.origin_template = args
        self.msg: Union[MessageSession, None] = msg
        self.options_desc = []
        self.lang = self.msg.locale if self.msg else Locale(default_locale)
        help_docs = {}
        for match in (
            args.command_list.set if not self.msg else args.command_list.get(
                self.msg.target.target_from)):
            if match.help_doc:
                for m in match.help_doc:
                    help_docs[m] = {'priority': match.priority, 'meta': match}
            else:
                help_docs[''] = {'priority': match.priority, 'meta': match}
            if match.options_desc:
                for m in match.options_desc:
                    desc = match.options_desc[m]
                    if locale_str := re.findall(r'\{(.*)}', desc):
                        for l in locale_str:
                            desc = desc.replace(f'{{{l}}}', self.lang.t(l, fallback_failed_prompt=False))
                    self.options_desc.append(f'{m} {desc}')
        self.args: Dict[Union[Template, ''], dict] = help_docs

    def return_formatted_help_doc(self) -> str:
        if not self.args:
            return ''
        lst = []
        format_args = templates_to_str([args for args in self.args if args != ''], with_desc=True)
        for x in format_args:
            if locale_str := re.findall(r'\{(.*)}', x):
                for l in locale_str:
                    x = x.replace(f'{{{l}}}', self.lang.t(l, fallback_failed_prompt=False))
            x = f'{self.command_prefixes[0]}{self.bind_prefix} {x}'
            lst.append(x)
        args = '\n'.join(y for y in lst)
        if self.options_desc:
            options_desc = self.options_desc.copy()
            options_desc_localed = []
            for x in options_desc:
                if locale_str := re.findall(r'\{(.*)}', x):
                    for l in locale_str:
                        x = x.replace(f'{{{l}}}', self.lang.t(l, fallback_failed_prompt=False))
                options_desc_localed.append(x)
            args += f'\n{self.lang.t("core.help.options")}\n' + '\n'.join(options_desc_localed)
        return args

    def parse(self, command):
        if not self.args:
            return None
        command = re.sub(r'[“”]', '"', command)
        try:
            split_command = shlex.split(command)
        except ValueError:
            split_command = command.split(' ')
        Logger.debug(split_command)
        try:
            if not self.origin_template.command_list.set:
                if len(split_command) == 1:
                    return None, None
            else:
                if len(split_command) == 1:
                    if '' in self.args:
                        return self.args['']['meta'], None
                    for arg in self.args:
                        if len(arg.args) == 1 and isinstance(arg.args[0], DescPattern):
                            return self.args[arg]['meta'], None
                    raise InvalidCommandFormatError
                else:
                    base_match = parse_argv(split_command[1:], [args for args in self.args if args != ''])
                    return self.args[base_match.original_template]['meta'], base_match.args

        except InvalidCommandFormatError:
            traceback.print_exc()
            raise InvalidCommandFormatError
