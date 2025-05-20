from attrs import define, field, Converter
from copy import deepcopy

from apscheduler.triggers.combining import AndTrigger, OrTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from core.utils.list import convert2lst
from .component_matches import *


def alias_converter(value, _self) -> dict:
    if isinstance(value, str):
        return {value: _self.bind_prefix}
    if isinstance(value, (tuple, list)):
        return {x: _self.bind_prefix for x in value}
    return value


@define
class Module:
    bind_prefix: str
    alias: dict = field(converter=Converter(alias_converter, takes_self=True))
    recommend_modules: list = field(converter=convert2lst)
    developers: list = field(converter=convert2lst)
    available_for: list = field(default=["*"], converter=convert2lst)
    exclude_from: list = field(default=[], converter=convert2lst)
    support_languages: list = field(default=None, converter=convert2lst)
    desc: str = ""
    required_admin: bool = False
    base: bool = False
    doc: bool = False
    hidden: bool = False
    load: bool = True
    rss: bool = False
    required_superuser: bool = False
    required_base_superuser: bool = False
    command_list: CommandMatches = CommandMatches.init()
    regex_list: RegexMatches = RegexMatches.init()
    schedule_list: ScheduleMatches = ScheduleMatches.init()
    hooks_list: HookMatches = HookMatches.init()

    @classmethod
    def assign(cls, **kwargs):
        return deepcopy(cls(**kwargs))

    def to_dict(self):
        return {
            "bind_prefix": self.bind_prefix,
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
        }


__all__ = [
    "Module",
    "AndTrigger",
    "OrTrigger",
    "DateTrigger",
    "CronTrigger",
    "IntervalTrigger",
]
