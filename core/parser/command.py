import re
import shlex
import traceback
from typing import Union

from core.docopt import docopt, DocoptExit
from core.elements import Command, Option, Schedule, StartUp, RegexCommand, command_prefix, MessageSession

command_prefix_first = command_prefix[0]


class InvalidHelpDocTypeError(BaseException):
    def __init__(self, *args, **kwargs):
        pass


class InvalidCommandFormatError(BaseException):
    def __init__(self, *args, **kwargs):
        pass


class CommandParser:
    def __init__(self, args: Union[str, list, tuple, Command, Option, Schedule, StartUp, RegexCommand], prefix=None,
                 msg: MessageSession = None):
        """
        Format: https://github.com/jazzband/docopt-ng#usage-pattern-format
        * {} - Detail help information
        """
        self.bind_prefix = prefix
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
        elif isinstance(args, (Schedule, StartUp, Option, RegexCommand)):
            args = None
        if args is None:
            self.args = None
            return
        if isinstance(args, str):
            args = [args]
            self.args_raw = args
        elif isinstance(args, tuple):
            args = list(args)
        if isinstance(args, list):
            arglst_raw = []
            arglst = []
            for x in args:
                split = x.split(' ')[0]
                if self.bind_prefix is not None:
                    if split not in [command_prefix_first + self.bind_prefix, self.bind_prefix]:
                        x = f'{command_prefix_first}{self.bind_prefix} {x}'
                arglst_raw.append(x)
                match_detail_help = re.match('(.*){.*}$', x, re.M | re.S)
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
        if isinstance(args_raw, list):
            arglst = []
            for x in args_raw:
                if x[0] not in command_prefix:
                    x = command_prefix_first + x
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
        try:
            if not isinstance(self.origin_template, Command):
                if len(split_command) == 1:
                    return None
                return docopt(self.args, argvs=split_command[1:], default_help=False)
            else:
                if len(split_command) == 1:
                    for match in (self.origin_template.match_list.set if self.msg is None else
                    self.origin_template.match_list.get(self.msg.target.targetFrom)):
                        if match.help_doc is None:
                            return match, None
                    raise InvalidCommandFormatError
                else:
                    base_match = docopt(self.args, argvs=split_command[1:], default_help=False)
                    for match in (self.origin_template.match_list.set if self.msg is None else
                    self.origin_template.match_list.get(self.msg.target.targetFrom)):
                        if match.help_doc is None:
                            continue
                        try:
                            sub_args = CommandParser(match.help_doc, prefix=self.bind_prefix).args
                            if sub_args is not None:
                                get_parse = docopt(sub_args,
                                                   argvs=split_command[1:], default_help=False)
                            else:
                                continue
                        except DocoptExit:
                            continue
                        correct = True
                        for g in get_parse:
                            if g not in base_match or get_parse[g] != base_match[g]:
                                correct = False
                        if correct:
                            return match, get_parse


        except DocoptExit:
            traceback.print_exc()
            raise InvalidCommandFormatError
