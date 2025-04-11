import re
from typing import Callable, Union, List

from apscheduler.triggers.combining import AndTrigger, OrTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from core.parser.args import Template

from attrs import define, field
from core.utils.list import convert2lst


class ModuleMeta:
    pass


@define
class CommandMeta(ModuleMeta):
    function: Callable = None
    help_doc: List[Template] = field(default=[], converter=convert2lst)
    options_desc: dict = None
    required_admin: bool = False
    required_superuser: bool = False
    required_base_superuser: bool = False
    available_for: list = field(default=["*"], converter=convert2lst)
    exclude_from: list = field(default=[], converter=convert2lst)
    load: bool = True
    priority: int = 1


@define
class RegexMeta(ModuleMeta):
    function: Callable = None
    pattern: Union[str, re.Pattern] = None
    mode: str = None
    desc: str = None
    required_admin: bool = False
    required_superuser: bool = False
    required_base_superuser: bool = False
    available_for: list = field(default=["*"], converter=convert2lst)
    exclude_from: list = field(default=[], converter=convert2lst)
    flags: re.RegexFlag = 0
    load: bool = True
    logging: bool = True
    show_typing: bool = True
    text_only: bool = True


@define
class ScheduleMeta(ModuleMeta):
    trigger: Union[AndTrigger, OrTrigger, DateTrigger, CronTrigger, IntervalTrigger]
    function: Callable = None


@define
class HookMeta(ModuleMeta):
    function: Callable = None
    name: str = None


__all__ = ["ModuleMeta", "CommandMeta", "RegexMeta", "ScheduleMeta", "HookMeta"]
