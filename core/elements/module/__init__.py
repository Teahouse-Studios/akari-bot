from typing import Callable, Union

from apscheduler.triggers.combining import AndTrigger, OrTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from .matches import *


class Command:
    def __init__(self,
                 bind_prefix: str,
                 alias: Union[str, list, tuple, dict] = None,
                 desc: str = None,
                 recommend_modules: Union[str, list, tuple] = None,
                 developers: Union[str, list, tuple] = None,
                 required_admin: bool = False,
                 base: bool = False,
                 required_superuser: bool = False):
        self.bind_prefix = bind_prefix
        self.alias = alias
        self.desc = desc
        self.recommend_modules = recommend_modules
        self.developers = developers
        self.required_admin = required_admin
        self.base = base
        self.required_superuser = required_superuser
        self.match_list = CommandMatches()


class RegexCommand:
    def __init__(self,
                 bind_prefix: str,
                 alias: Union[str, list, tuple, dict] = None,
                 desc: str = None,
                 recommend_modules: Union[str, list, tuple] = None,
                 developers: Union[str, list, tuple] = None,
                 required_admin: bool = False,
                 base: bool = False,
                 required_superuser: bool = False):
        self.bind_prefix = bind_prefix
        self.alias = alias
        self.desc = desc
        self.recommend_modules = recommend_modules
        self.developers = developers
        self.required_admin = required_admin
        self.base = base
        self.required_superuser = required_superuser
        self.match_list = RegexMatches()


class Option:
    def __init__(self,
                 bind_prefix: str,
                 desc: str = None,
                 alias: Union[str, list, tuple, dict] = None,
                 recommend_modules: Union[str, list, tuple] = None,
                 developers: Union[str, list, tuple] = None,
                 required_superuser: bool = False,
                 required_admin: bool = False):
        self.bind_prefix = bind_prefix
        self.desc = desc
        self.alias = alias
        self.recommend_modules = recommend_modules
        self.developers = developers
        self.required_superuser = required_superuser
        self.required_admin = required_admin
        self.match_list = None


class Schedule:
    def __init__(self,
                 function: Callable,
                 trigger: [AndTrigger, OrTrigger, DateTrigger, CronTrigger, IntervalTrigger],
                 bind_prefix: str,
                 desc: str = None,
                 alias: Union[str, list, tuple, dict] = None,
                 recommend_modules: Union[str, list, tuple] = None,
                 developers: Union[str, list, tuple] = None,
                 required_superuser: bool = False,
                 ):
        self.function = function
        self.trigger = trigger
        self.bind_prefix = bind_prefix
        self.desc = desc
        self.alias = alias
        self.recommend_modules = recommend_modules
        self.developers = developers
        self.required_superuser = required_superuser


class StartUp:
    def __init__(self,
                 function: Callable,
                 bind_prefix: str,
                 desc: str = None,
                 alias: Union[str, list, tuple, dict] = None,
                 recommend_modules: Union[str, list, tuple] = None,
                 developers: Union[str, list, tuple] = None,
                 required_superuser: bool = False,
                 ):
        self.function = function
        self.bind_prefix = bind_prefix
        self.desc = desc
        self.alias = alias
        self.recommend_modules = recommend_modules
        self.developers = developers
        self.required_superuser = required_superuser


__all__ = ["Command", "RegexCommand", "Option", "Schedule", "StartUp", "AndTrigger", "OrTrigger", "DateTrigger",
           "CronTrigger", "IntervalTrigger"]
