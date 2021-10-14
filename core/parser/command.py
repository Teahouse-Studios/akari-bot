import re
import shlex
from typing import Union

from core.docopt import docopt, DocoptExit
from core.elements import Command, Option, Schedule, StartUp, RegexCommand


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
        if isinstance(args, Command):
            if args.help_doc is not None:
                args = args.help_doc
            if args.desc is not None:
                args = args.desc
                self.desc = True
        if isinstance(args, (Option, Schedule, StartUp, RegexCommand)):
            if args.desc is not None:
                args = args.desc
                self.desc = True
        if isinstance(args, str):
            args = [args]
        if isinstance(args, (list, tuple)):
            arglst = []
            for x in args:
                match_detail_help = re.match('(.*){.*}$', x)
                if match_detail_help:
                    x = match_detail_help.group(1)
                arglst.append(x)
            self.args = 'Usage:\n  ' + '\n  '.join(y for y in arglst)
        else:
            raise InvalidHelpDocTypeError
        self.args_raw = args

    def return_formatted_help_doc(self) -> str:
        args_raw = self.args_raw
        if self.desc:
            return args_raw
        if isinstance(args_raw, str):
            args_raw = [args_raw]
        if isinstance(args_raw, (list, tuple)):
            arglst = []
            for x in args_raw:
                match_detail_help = re.match('(.*){(.*)}$', x)
                if match_detail_help:
                    x = f'{match_detail_help.group(1)} - {match_detail_help.group(2)}'
                arglst.append(x)
            args = f'用法：\n  ' + '\n  '.join(y for y in arglst)
        else:
            raise InvalidHelpDocTypeError
        return args

    def parse(self, command):
        if self.desc:
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
