from typing import Union, Dict, List

from apscheduler.triggers.combining import AndTrigger, OrTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from .component_matches import *

from core.utils.list import convert2lst

from attrs import define, field, Converter

from copy import deepcopy


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
    desc: Union[str] = ""
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


__all__ = [
    "Module",
    "AndTrigger",
    "OrTrigger",
    "DateTrigger",
    "CronTrigger",
    "IntervalTrigger",
]
