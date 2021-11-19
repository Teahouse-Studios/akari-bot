from typing import Callable, Union, Dict, List

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
        self.bind_prefix: str = bind_prefix
        if isinstance(alias, str):
            alias = {alias: bind_prefix}
        elif isinstance(alias, (tuple, list)):
            alias = {x: bind_prefix for x in alias}
        self.alias: Dict[str, str] = alias
        self.desc: str = desc
        if isinstance(recommend_modules, str):
            recommend_modules = [recommend_modules]
        elif isinstance(recommend_modules, tuple):
            recommend_modules = list(recommend_modules)
        self.recommend_modules: List[str] = recommend_modules
        if isinstance(developers, str):
            developers = [developers]
        elif isinstance(developers, tuple):
            developers = list(developers)
        self.developers: List[str] = developers
        self.required_admin: bool = required_admin
        self.base: bool = base
        self.required_superuser: bool = required_superuser
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
        self.bind_prefix: str = bind_prefix
        if isinstance(alias, str):
            alias = {alias: bind_prefix}
        elif isinstance(alias, (tuple, list)):
            alias = {x: bind_prefix for x in alias}
        self.alias: Dict[str, str] = alias
        self.desc: str = desc
        if isinstance(recommend_modules, str):
            recommend_modules = [recommend_modules]
        elif isinstance(recommend_modules, tuple):
            recommend_modules = list(recommend_modules)
        self.recommend_modules: List[str] = recommend_modules
        if isinstance(developers, str):
            developers = [developers]
        elif isinstance(developers, tuple):
            developers = list(developers)
        self.developers: List[str] = developers
        self.required_admin: bool = required_admin
        self.base: bool = base
        self.required_superuser: bool = required_superuser
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
        self.bind_prefix: str = bind_prefix
        if isinstance(alias, str):
            alias = {alias: bind_prefix}
        elif isinstance(alias, (tuple, list)):
            alias = {x: bind_prefix for x in alias}
        self.alias: Dict[str, str] = alias
        self.desc: str = desc
        if isinstance(recommend_modules, str):
            recommend_modules = [recommend_modules]
        elif isinstance(recommend_modules, tuple):
            recommend_modules = list(recommend_modules)
        self.recommend_modules: List[str] = recommend_modules
        if isinstance(developers, str):
            developers = [developers]
        elif isinstance(developers, tuple):
            developers = list(developers)
        self.developers: List[str] = developers
        self.required_admin: bool = required_admin
        self.required_superuser: bool = required_superuser
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
        self.function: Callable = function
        self.trigger: [AndTrigger, OrTrigger, DateTrigger, CronTrigger, IntervalTrigger] = trigger
        self.bind_prefix: str = bind_prefix
        self.desc: str = desc
        if isinstance(alias, str):
            alias = {alias: bind_prefix}
        elif isinstance(alias, (tuple, list)):
            alias = {x: bind_prefix for x in alias}
        self.alias: Dict[str, str] = alias
        if isinstance(recommend_modules, str):
            recommend_modules = [recommend_modules]
        elif isinstance(recommend_modules, tuple):
            recommend_modules = list(recommend_modules)
        self.recommend_modules: List[str] = recommend_modules
        if isinstance(developers, str):
            developers = [developers]
        elif isinstance(developers, tuple):
            developers = list(developers)
        self.developers: List[str] = developers
        self.required_superuser: bool = required_superuser


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
        self.function: Callable = function
        self.bind_prefix: str = bind_prefix
        self.desc: str = desc
        if isinstance(alias, str):
            alias = {alias: bind_prefix}
        elif isinstance(alias, (tuple, list)):
            alias = {x: bind_prefix for x in alias}
        self.alias: Dict[str, str] = alias
        if isinstance(recommend_modules, str):
            recommend_modules = [recommend_modules]
        elif isinstance(recommend_modules, tuple):
            recommend_modules = list(recommend_modules)
        self.recommend_modules: List[str] = recommend_modules
        if isinstance(developers, str):
            developers = [developers]
        elif isinstance(developers, tuple):
            developers = list(developers)
        self.developers = developers
        self.required_superuser: bool = required_superuser


__all__ = ["Command", "RegexCommand", "Option", "Schedule", "StartUp", "AndTrigger", "OrTrigger", "DateTrigger",
           "CronTrigger", "IntervalTrigger"]
