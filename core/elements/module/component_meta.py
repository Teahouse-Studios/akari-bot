import re
from typing import Callable, Union


class Meta:
    def __init__(self, **kwargs):
        ...


class CommandMeta:
    def __init__(self,
                 function: Callable = None,
                 help_doc: Union[str, list, tuple] = None,
                 options_desc: dict = None,
                 required_admin: bool = False,
                 required_superuser: bool = False,
                 available_for: Union[str, list, tuple] = '*',
                 exclude_from: Union[str, list, tuple] = '',
                 ):
        self.function = function
        if isinstance(help_doc, str):
            help_doc = [help_doc]
        elif isinstance(help_doc, tuple):
            help_doc = list(help_doc)
        self.help_doc: list = help_doc
        self.options_desc = options_desc
        self.required_admin = required_admin
        self.required_superuser = required_superuser
        if isinstance(available_for, str):
            available_for = [available_for]
        elif isinstance(available_for, tuple):
            available_for = list(available_for)
        if isinstance(exclude_from, str):
            exclude_from = [exclude_from]
        elif isinstance(exclude_from, tuple):
            exclude_from = list(exclude_from)
        self.available_for = available_for
        self.exclude_from = exclude_from


class RegexMeta:
    def __init__(self,
                 function: Callable = None,
                 pattern: str = None,
                 mode: str = None,
                 flags: re.RegexFlag = 0,
                 show_typing: bool = True,
                 ):
        self.function = function
        self.pattern = pattern
        self.mode = mode
        self.flags = flags
        self.show_typing = show_typing


class ScheduleMeta:
    def __init__(self,
                 function: Callable = None
                 ):
        self.function = function


__all__ = ["Meta", "CommandMeta", "RegexMeta", "ScheduleMeta"]
