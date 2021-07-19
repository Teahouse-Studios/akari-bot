import shlex
from core.docopt import docopt


class InvalidCommandFormatError(BaseException):
    def __init__(self, *args, **kwargs):
        pass


class CommandParser:
    def __init__(self, args: [str, list, tuple]):
        if isinstance(args, str):
            self.args = f'Usage:\n  {args}'
        elif isinstance(args, (list, tuple)):
            self.args = f'Usage:\n  ' + '\n  '.join(x for x in args)
        else:
            raise InvalidCommandFormatError

    def parse(self, command):
        return docopt(self.args, argvs=shlex.split(command)[1:], default_help=False)
