import re
from enum import Enum
from typing import Callable

from apscheduler.triggers.combining import AndTrigger, OrTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from attrs import define, field

from core.builtins.parser.args import Template
from core.builtins.types import MessageElement
from core.utils.func import convert_list


class ModuleMeta:
    pass


@define
class CommandMeta(ModuleMeta):
    function: Callable = None
    command_template: list[Template] = field(default=[], converter=convert_list)
    options_desc: dict = None
    required_admin: bool = False
    required_superuser: bool = False
    required_base_superuser: bool = False
    available_for: list = field(default=["*"], converter=convert_list)
    exclude_from: list = field(default=[], converter=convert_list)
    load: bool = True
    priority: int = 1


class RegexMode(Enum):
    USERCHOOSE = "U"
    MATCH = "M"
    FINDALL = "A"

    @classmethod
    def fromstr(cls, string: "RegexMode | str"):
        if isinstance(string, RegexMode):
            return string
        string = string.upper()
        if string in ["U", "USERCHOOSE"]:
            return cls.USERCHOOSE
        if string in ["M", "MATCH"]:
            return cls.MATCH
        if string in ["A", "FINDALL"]:
            return cls.FINDALL
        raise ValueError()

@define
class RegexMeta(ModuleMeta):
    function: Callable | None = None
    pattern: str | re.Pattern | None = None
    mode: RegexMode | None = None
    desc: str | None = None
    required_admin: bool = False
    required_superuser: bool = False
    required_base_superuser: bool = False
    available_for: list = field(default=["*"], converter=convert_list)
    exclude_from: list = field(default=[], converter=convert_list)
    flags: re.RegexFlag = re.NOFLAG
    load: bool = True
    logging: bool = True
    show_typing: bool = True
    text_only: bool = True
    element_filter: tuple[MessageElement, ...] | None = None


@define
class ScheduleMeta(ModuleMeta):
    trigger: AndTrigger | OrTrigger | DateTrigger | CronTrigger | IntervalTrigger
    function: Callable | None = None


@define
class HookMeta(ModuleMeta):
    function: Callable | None = None
    name: str | None = None


__all__ = ["ModuleMeta", "CommandMeta", "RegexMeta", "ScheduleMeta", "HookMeta", "RegexMode"]
