import shlex
from core.docopt import docopt


class InvalidCommandFormatError:
    def __init__(self, *args, **kwargs):
        pass


class CommandParser:
    def __init__(self, args: str):
        self.args = 'Usage:\n' + args

    def parse(self, command):
        return docopt(self.args, argvs=shlex.split(command)[1:], help=False)