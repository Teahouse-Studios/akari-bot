from typing import Callable
import re


class Module:
    def __init__(self,
                 function: Callable,
                 bind_prefix: str,
                 alias: [str, list, tuple],
                 help_doc: [str, list, tuple, None],
                 need_self_process: bool,
                 need_admin: bool,
                 is_base_function: bool,
                 need_superuser: bool,
                 is_regex_function: bool,
                 autorun: bool):
        self.function = function
        self.bind_prefix = bind_prefix
        self.alias = alias
        self.help_doc = help_doc
        self.need_self_process = need_self_process
        self.need_admin = need_admin
        self.is_base_function = is_base_function
        self.need_superuser = need_superuser
        self.is_regex_function = is_regex_function
        self.autorun = autorun


class Option:
    def __init__(self, bind_prefix,
                 help_doc,
                 alias,
                 need_superuser,
                 need_admin):
        self.bind_prefix = bind_prefix
        self.help_doc = help_doc
        self.alias = alias
        self.need_superuser = need_superuser
        self.need_admin = need_admin
