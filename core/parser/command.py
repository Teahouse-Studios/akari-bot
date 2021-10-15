import re
import shlex
from typing import Union

from core.docopt import docopt, DocoptExit
from core.elements import Command, Option, Schedule, StartUp, RegexCommand, command_prefix


command_prefix_first = command_prefix[0]


class InvalidHelpDocTypeError(BaseException):
    def __init__(self, *args, **kwargs):
        pass


class InvalidCommandFormatError(BaseException):
    def __init__(self, *args, **kwargs):
        pass


class CommandParser:
    def __init__(self, args: Union[str, list, tuple, Command, Option, Schedule, StartUp, RegexCommand]):
        """
        Format: https://github.com/jazzband/docopt-ng#usage-pattern-format
        * {} - Detail help information
        """
        self.desc = False
        self.bind_prefix = None
        if isinstance(args, Command):
            self.bind_prefix = args.bind_prefix
            if args.help_doc is not None:
                args = args.help_doc
            elif args.desc is not None:
                args = args.desc
                self.desc = True
            else:
                args = None
        elif isinstance(args, (Option, Schedule, StartUp, RegexCommand)):
            self.bind_prefix = args.bind_prefix
            if args.desc is not None:
                args = args.desc
                self.desc = True
            else:
                args = None
        if args is None:
            self.args = args
            return
        if isinstance(args, str):
            args = [args]
            self.args_raw = args
        if self.desc:
            self.args = args
            return
        if isinstance(args, (list, tuple)):
            arglst_raw = []
            arglst = []
            for x in args:
                split = x.split(' ')[0]
                if self.bind_prefix is not None:
                    if split not in [command_prefix_first + self.bind_prefix, self.bind_prefix]:
                        x = f'{command_prefix_first}{self.bind_prefix} {x}'
                arglst_raw.append(x)
                match_detail_help = re.match('(.*){.*}$', x)
                if match_detail_help:
                    x = match_detail_help.group(1)
                arglst.append(x)
            self.args_raw = arglst_raw
            self.args = 'Usage:\n  ' + '\n  '.join(y for y in arglst)
        else:
            raise InvalidHelpDocTypeError

    def return_formatted_help_doc(self) -> str:
        if self.args is None:
            return '（此模块没有帮助信息）'
        args_raw = self.args_raw
        if isinstance(args_raw, str):
            args_raw = [args_raw]
        if self.desc:
            return '说明：\n' + '\n  '.join(y for y in args_raw)
        if isinstance(args_raw, (list, tuple)):
            arglst = []
            for x in args_raw:
                if x[0] not in command_prefix:
                    x = command_prefix_first + x
                match_detail_help = re.match('(.*){(.*)}$', x)
                if match_detail_help:
                    x = f'{match_detail_help.group(1)}- {match_detail_help.group(2)}'
                arglst.append(x)
            args = f'用法：\n  ' + '\n  '.join(y for y in arglst)
        else:
            raise InvalidHelpDocTypeError
        return args

    def parse(self, command):
        if self.desc or self.args is None:
            return None
        command = re.sub('“', '"', re.sub('”', '"', command))
        try:
            split_command = shlex.split(command)
        except ValueError:
            split_command = command.split(' ')
        if len(split_command) == 1:
            return None
        try:
            return docopt(self.args, argvs=split_command[1:], default_help=False)
        except DocoptExit:
            raise InvalidCommandFormatError
