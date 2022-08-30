import copy
import re
import shlex
import traceback
from typing import Union, Dict

from core.elements import Command, MessageSession
from core.exceptions import InvalidCommandFormatError
from .args import parse_argv, Template, templates_to_str, DescPattern
from ..logger import Logger


class CommandParser:
    def __init__(self, args: Command, command_prefixes: list,
                 bind_prefix=None,
                 msg: MessageSession = None):
        args = copy.deepcopy(args)
        self.command_prefixes = command_prefixes
        self.bind_prefix = bind_prefix
        self.origin_template = args
        self.msg: Union[MessageSession, None] = msg
        self.options_desc = []
        help_docs = {}
        for match in (args.match_list.set if self.msg is None else args.match_list.get(self.msg.target.targetFrom)):
            if match.help_doc:
                for m in match.help_doc:
                    help_docs[m] = {'priority': match.priority, 'meta': match}
            else:
                help_docs[''] = {'priority': match.priority, 'meta': match}
            if match.options_desc is not None:
                for m in match.options_desc:
                    self.options_desc.append(f'{m}  {match.options_desc[m]}')
        self.args: Dict[Union[Template, ''], dict] = help_docs

    def return_formatted_help_doc(self) -> str:
        if not self.args:
            return '（此模块没有帮助信息）'
        lst = []
        format_args = templates_to_str([args for args in self.args if args != ''], with_desc=True)
        for x in format_args:
            x = f'{self.command_prefixes[0]}{self.bind_prefix} {x}'
            lst.append(x)
        args = '\n'.join(y for y in lst)
        if self.options_desc:
            args += '\n参数：\n' + '\n'.join(self.options_desc)
        return args

    def parse(self, command):
        if self.args is None:
            return None
        command = re.sub(r'[“”]', '"', command)
        try:
            split_command = shlex.split(command)
        except ValueError:
            split_command = command.split(' ')
        Logger.debug(split_command)
        try:
            if not isinstance(self.origin_template, Command):
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
