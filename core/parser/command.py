import re
import shlex
import traceback
from typing import Union

from core.elements import Command, Schedule, StartUp, RegexCommand, MessageSession
from core.exceptions import InvalidCommandFormatError, InvalidHelpDocTypeError

from .args import parse_template, parse_argv
from ..logger import Logger


class CommandParser:
    def __init__(self, args: Union[str, list, tuple, Command, Schedule, StartUp, RegexCommand], command_prefixes: list,
                 bind_prefix=None,
                 msg: MessageSession = None):
        """
        Format: https://github.com/jazzband/docopt-ng#usage-pattern-format
        * {} - Detail help information
        """
        self.command_prefixes = command_prefixes
        self.bind_prefix = bind_prefix
        self.origin_template = args
        self.msg: Union[MessageSession, None] = msg
        self.options_desc = []
        if isinstance(args, Command):
            self.bind_prefix = args.bind_prefix
            help_doc_list = []
            none_doc = True
            for match in (args.match_list.set if self.msg is None else args.match_list.get(self.msg.target.targetFrom)):
                if match.help_doc is not None:
                    none_doc = False
                    help_doc_list = help_doc_list + match.help_doc
                if match.options_desc is not None:
                    for m in match.options_desc:
                        self.options_desc.append(f'{m}  {match.options_desc[m]}')
            if not none_doc:
                args = help_doc_list
            else:
                args = None
        elif isinstance(args, (Schedule, StartUp, RegexCommand)):
            args = None
        if args is None:
            self.args = None
            return
        if isinstance(args, str):
            args = [args]
        elif isinstance(args, tuple):
            args = list(args)
        if isinstance(args, list):
            self.args = args
        else:
            raise InvalidHelpDocTypeError

    def return_formatted_help_doc(self) -> str:
        if self.args is None:
            return '（此模块没有帮助信息）'
        if isinstance(self.args, list):
            arglst = []
            for x in self.args:
                if not x.startswith([self.command_prefixes[0] + self.bind_prefix]):
                    x = f'{self.command_prefixes[0]}{self.bind_prefix} {x}'
                match_detail_help = re.match('(.*){(.*)}$', x, re.M | re.S)
                if match_detail_help:
                    x = f'{match_detail_help.group(1)}- {match_detail_help.group(2)}'
                arglst.append(x)
            args = '\n'.join(y for y in arglst)
        else:
            raise InvalidHelpDocTypeError
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
        argv_template = parse_template(self.args)
        try:
            if not isinstance(self.origin_template, Command):
                if len(split_command) == 1:
                    return None
                return parse_argv(split_command[1:], argv_template)
            else:
                if len(split_command) == 1:
                    for match in (self.origin_template.match_list.set if self.msg is None else
                    self.origin_template.match_list.get(self.msg.target.targetFrom)):
                        if match.help_doc is None:
                            return match, None
                    raise InvalidCommandFormatError
                else:
                    base_match = parse_argv(split_command[1:], argv_template)
                    for match in (self.origin_template.match_list.set if self.msg is None else
                    self.origin_template.match_list.get(self.msg.target.targetFrom)):
                        if match.help_doc is None:
                            continue
                        try:
                            sub_args = CommandParser(match.help_doc, bind_prefix=self.bind_prefix,
                                                     command_prefixes=self.command_prefixes).args
                            if sub_args is not None:
                                sub_args = parse_template(sub_args)
                                Logger.debug(sub_args)
                                get_parse = parse_argv(split_command[1:], sub_args)
                            else:
                                continue
                        except InvalidCommandFormatError:
                            continue
                        correct = True
                        for g in get_parse:
                            if g not in base_match or get_parse[g] != base_match[g]:
                                correct = False
                        if correct:
                            return match, get_parse

        except InvalidCommandFormatError:
            traceback.print_exc()
            raise InvalidCommandFormatError
