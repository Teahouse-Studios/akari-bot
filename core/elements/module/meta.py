import re
from typing import Callable, Union


class Meta:
    def __init__(self, **kwargs):
        ...


class CommandMeta:
    def __init__(self,
                 function: Callable = None,
                 help_doc: Union[str, list, tuple] = None,
                 required_admin: bool = False,
                 required_superuser: bool = False
                 ):
        self.function = function
        if isinstance(help_doc, str):
            help_doc = [help_doc]
        elif isinstance(help_doc, tuple):
            help_doc = list(help_doc)
        self.help_doc: list = help_doc
        self.required_admin = required_admin
        self.required_superuser = required_superuser


class RegexMeta:
    def __init__(self,
                 function: Callable = None,
                 pattern: str = None,
                 mode: str = None,
                 flags: re.RegexFlag = 0,
                 ):
        self.function = function
        self.pattern = pattern
        self.mode = mode
        self.flags = flags


class ScheduleMeta:
    def __init__(self,
                 function: Callable = None
                 ):
        self.function = function


__all__ = ["Meta", "CommandMeta", "RegexMeta", "ScheduleMeta"]
