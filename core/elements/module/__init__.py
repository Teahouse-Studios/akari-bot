from typing import Callable
from apscheduler.triggers.combining import AndTrigger, OrTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger


class Command:
    def __init__(self,
                 function: Callable,
                 bind_prefix: str,
                 alias: [str, list, tuple] = None,
                 help_doc: [str, list, tuple] = None,
                 desc: str = None,
                 need_self_process: bool = False,
                 need_admin: bool = False,
                 is_base_function: bool = False,
                 need_superuser: bool = False,
                 is_regex_function: bool = False,
                 autorun: bool = False):
        self.function = function
        self.bind_prefix = bind_prefix
        self.alias = alias
        self.help_doc = help_doc
        self.desc = desc
        self.need_self_process = need_self_process
        self.need_admin = need_admin
        self.is_base_function = is_base_function
        self.need_superuser = need_superuser
        self.is_regex_function = is_regex_function
        self.autorun = autorun


class Option:
    def __init__(self,
                 bind_prefix: str,
                 desc: str = None,
                 help_doc: [str, list, tuple] = None,
                 alias: [str, list, tuple] = None,
                 need_superuser: bool = False,
                 need_admin: bool = False):
        self.bind_prefix = bind_prefix
        self.help_doc = help_doc
        self.desc = desc
        self.alias = alias
        self.need_superuser = need_superuser
        self.need_admin = need_admin


class Schedule:
    def __init__(self,
                 function: Callable,
                 trigger: [AndTrigger, OrTrigger, DateTrigger, CronTrigger, IntervalTrigger],
                 bind_prefix: str,
                 desc: str = None,
                 help_doc: [str, list, tuple] = None,
                 alias: [str, list, tuple] = None,
                 need_superuser: bool = False,
                 need_admin: bool = False
                 ):
        self.function = function
        self.trigger = trigger
        self.bind_prefix = bind_prefix
        self.desc = desc
        self.help_doc = help_doc
        self.alias = alias
        self.need_superuser = need_superuser
        self.need_admin = need_admin


__all__ = ["Command", "Option", "Schedule", "AndTrigger", "OrTrigger", "DateTrigger", "CronTrigger", "IntervalTrigger"]
