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
            help_docs = {}
            none_doc = True
            for match in (args.match_list.set if self.msg is None else args.match_list.get(self.msg.target.targetFrom)):
                print(match.__dict__)
                if match.help_doc is not None:
                    none_doc = False
                    if match.help_doc:
                        for m in match.help_doc:
                            help_docs[m] = {'priority': match.priority, 'meta': match}
                    else:
                        help_docs[''] = {'priority': match.priority, 'meta': match}
                if match.options_desc is not None:
                    for m in match.options_desc:
                        self.options_desc.append(f'{m}  {match.options_desc[m]}')
            if not none_doc:
                args = help_docs
            else:
                args = None
        elif isinstance(args, (Schedule, StartUp, RegexCommand)):
            args = None
        if args is None:
            self.args = None
            return

        async def empty_func():
            pass

        if isinstance(args, str):
            args = {args: {'priority': 1, 'function': empty_func()}}
        elif isinstance(args, tuple):
            args = list(args)
        if isinstance(args, list):
            args = {arg: {'priority': 1, 'function': empty_func()} for arg in args}
        self.args = args
        print(self.args)

    def return_formatted_help_doc(self) -> str:
        if not self.args:
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
        try:
            if not isinstance(self.origin_template, Command):
                if len(split_command) == 1:
                    return None, None
            else:
                if len(split_command) == 1:
                    print(self.args)
                    if '' in self.args:
                        return self.args['']['meta'], None
                    raise InvalidCommandFormatError
                else:
                    base_match = parse_argv(split_command[1:], [args for args in self.args if args is not None])
                    return self.args[base_match.original_template]['meta'], base_match.args

        except InvalidCommandFormatError:
            traceback.print_exc()
            raise InvalidCommandFormatError
