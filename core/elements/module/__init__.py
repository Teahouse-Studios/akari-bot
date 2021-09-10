from typing import Callable, Union

from apscheduler.triggers.combining import AndTrigger, OrTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger


class Command:
    def __init__(self,
                 function: Callable,
                 bind_prefix: str,
                 alias: Union[str, list, tuple, dict] = None,
                 help_doc: Union[str, list, tuple] = None,
                 allowed_none: bool = True,
                 desc: str = None,
                 recommend_modules: Union[str, list, tuple] = None,
                 need_admin: bool = False,
                 is_base_function: bool = False,
                 need_superuser: bool = False,
                 is_regex_function: bool = False,
                 autorun: bool = False):
        self.function = function
        self.bind_prefix = bind_prefix
        self.alias = alias
        self.help_doc = help_doc
        self.allowed_none = allowed_none
        self.desc = desc
        self.recommend_modules = recommend_modules
        self.need_admin = need_admin
        self.is_base_function = is_base_function
        self.need_superuser = need_superuser
        self.is_regex_function = is_regex_function
        self.autorun = autorun


class Option:
    def __init__(self,
                 bind_prefix: str,
                 desc: str = None,
                 help_doc: Union[str, list, tuple] = None,
                 alias: Union[str, list, tuple, dict] = None,
                 recommend_modules: Union[str, list, tuple] = None,
                 need_superuser: bool = False,
                 need_admin: bool = False):
        self.bind_prefix = bind_prefix
        self.help_doc = help_doc
        self.desc = desc
        self.alias = alias
        self.allowed_none = True
        self.recommend_modules = recommend_modules
        self.need_superuser = need_superuser
        self.is_base_function = False
        self.is_regex_function = False
        self.need_admin = need_admin


class Schedule:
    def __init__(self,
                 function: Callable,
                 trigger: [AndTrigger, OrTrigger, DateTrigger, CronTrigger, IntervalTrigger],
                 bind_prefix: str,
                 desc: str = None,
                 help_doc: Union[str, list, tuple] = None,
                 alias: Union[str, list, tuple, dict] = None,
                 recommend_modules: Union[str, list, tuple] = None,
                 need_superuser: bool = False,
                 need_admin: bool = False
                 ):
        self.function = function
        self.trigger = trigger
        self.bind_prefix = bind_prefix
        self.desc = desc
        self.help_doc = help_doc
        self.allowed_none = True
        self.alias = alias
        self.recommend_modules = recommend_modules
        self.need_superuser = need_superuser
        self.is_base_function = False
        self.is_regex_function = False
        self.need_admin = need_admin


__all__ = ["Command", "Option", "Schedule", "AndTrigger", "OrTrigger", "DateTrigger", "CronTrigger", "IntervalTrigger"]
