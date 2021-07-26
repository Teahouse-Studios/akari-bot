import re
import shlex
from core.docopt import docopt, DocoptExit


class InvalidHelpDocTypeError(BaseException):
    def __init__(self, *args, **kwargs):
        pass


class InvalidCommandFormatError(BaseException):
    def __init__(self, *args, **kwargs):
        pass


class CommandParser:
    def __init__(self, args: [str, list, tuple]):
        """
        Format: https://github.com/jazzband/docopt-ng#usage-pattern-format
        * {} - Detail help information
        """
        self.args_raw = args
        if isinstance(args, str):
            args = [args]
        if isinstance(args, (list, tuple)):
            arglst = []
            for x in args:
                match_detail_help = re.match('(.*){.*}$', x)
                if match_detail_help:
                    x = match_detail_help.group(1)
                arglst.append(x)
            self.args = f'Usage:\n  ' + '\n  '.join(y for y in arglst)
        else:
            raise InvalidHelpDocTypeError

    def return_formatted_help_doc(self) -> str:
        args_raw = self.args_raw

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
        split_command = shlex.split(command)
        if len(split_command) == 1:
            return None
        try:
            return docopt(self.args, argvs=split_command[1:], default_help=False)
        except DocoptExit:
            raise InvalidCommandFormatError
