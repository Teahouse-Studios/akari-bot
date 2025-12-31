from copy import deepcopy

from apscheduler.triggers.combining import AndTrigger, OrTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from attrs import define, field, Converter

from core.utils.tools import convert_list
from .component_matches import *


def alias_converter(value, _self) -> dict:
    if isinstance(value, str):
        return {value: _self.module_name}
    if isinstance(value, (tuple, list)):
        return {x: _self.module_name for x in value}
    return value


@define
class Module:
    module_name: str
    alias: dict = field(converter=Converter(alias_converter, takes_self=True))
    recommend_modules: list = field(converter=convert_list)
    developers: list = field(converter=convert_list)
    available_for: list = field(default=["*"], converter=convert_list)
    exclude_from: list = field(default=[], converter=convert_list)
    support_languages: list = field(default=None, converter=convert_list)
    desc: str = ""
    required_admin: bool = False
    base: bool = False
    doc: bool = False
    hidden: bool = False
    load: bool = True
    rss: bool = False
    required_superuser: bool = False
    required_base_superuser: bool = False
    command_list: CommandMatches = field(factory=CommandMatches.init)
    regex_list: RegexMatches = field(factory=RegexMatches.init)
    schedule_list: ScheduleMatches = field(factory=ScheduleMatches.init)
    hooks_list: HookMatches = field(factory=HookMatches.init)
    _py_module_name: str = ""
    _db_load: bool = False

    @classmethod
    def assign(cls, **kwargs):
        obj = cls(**{k: v for k, v in kwargs.items() if not k.startswith("_")})
        obj._py_module_name = kwargs.get("_py_module_name", "")
        obj._db_load = kwargs.get("_db_load", False)
        return deepcopy(obj)

    def to_dict(self):
        return {
            "module_name": self.module_name,
            "alias": self.alias,
            "recommend_modules": self.recommend_modules,
            "developers": self.developers,
            "available_for": self.available_for,
            "exclude_from": self.exclude_from,
            "support_languages": self.support_languages,
            "desc": self.desc,
            "required_admin": self.required_admin,
            "base": self.base,
            "doc": self.doc,
            "hidden": self.hidden,
            "load": self.load,
            "rss": self.rss,
            "required_superuser": self.required_superuser,
            "required_base_superuser": self.required_base_superuser,
            "commands": len(self.command_list.set),
            "regexp": len(self.regex_list.set),
            "_py_module_name": self._py_module_name,
            "_db_load": self._db_load
        }


__all__ = [
    "Module",
    "AndTrigger",
    "OrTrigger",
    "DateTrigger",
    "CronTrigger",
    "IntervalTrigger",
]
