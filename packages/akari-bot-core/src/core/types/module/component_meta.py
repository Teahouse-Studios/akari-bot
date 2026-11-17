import re
from typing import Callable

from apscheduler.triggers.combining import AndTrigger, OrTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from attrs import define, field

from core.builtins.parser.args import Template
from core.builtins.types import MessageElement
from core.logger import Logger
from core.utils.func import convert_list


class ModuleMeta:
    pass


@define
class CommandMeta(ModuleMeta):
    # 注册组件时必定传入处理函数，默认值仅为满足 attrs 的字段顺序要求
    function: Callable = field(default=None)
    command_template: list[Template] = field(default=[], converter=convert_list)
    options_desc: dict | None = None
    required_admin: bool = False
    required_superuser: bool = False
    required_base_superuser: bool = False
    available_for: list = field(default=["*"], converter=convert_list)
    exclude_from: list = field(default=[], converter=convert_list)
    load: bool = True
    priority: int = 1


@define
class RegexMeta(ModuleMeta):
    function: Callable = field(default=None)
    pattern: str | re.Pattern | None = None
    mode: str | None = None
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
    trigger_once_startup: bool = False
    skip_long_message_confirm: bool = False
    # 注册期编译好的模式，避免每条消息都去 re 模块的全局缓存里查一次
    compiled: re.Pattern | None = field(default=None, init=False, repr=False, eq=False)

    def __attrs_post_init__(self):
        if isinstance(self.pattern, re.Pattern):
            if self.flags:
                # 已编译的模式无法再附加 flags，此前每次匹配都会因此抛错
                Logger.warning(f"Regex {self.pattern.pattern} is already compiled, the given flags are ignored.")
            self.compiled = self.pattern
        elif self.pattern is not None:
            self.compiled = re.compile(self.pattern, self.flags)


@define
class ScheduleMeta(ModuleMeta):
    trigger: AndTrigger | OrTrigger | DateTrigger | CronTrigger | IntervalTrigger
    function: Callable = field(default=None)


@define
class HookMeta(ModuleMeta):
    """模块 hook 元数据。"""

    function: Callable = field(default=None)
    name: str | None = None
    # 入口订阅字段；具名 hook 保持默认即可
    point: str | None = None
    priority: int = 100
    available_for: list = field(default=["*"], converter=convert_list)
    exclude_from: list = field(default=[], converter=convert_list)
    load: bool = True
    # 单次执行预算（秒）；<=0 表示不限时
    timeout: float = 5.0
    # server 作用域：免场景 enabled_modules，仍遵守全局停用与平台约束
    server_scope: bool = False


@define
class EventMeta(ModuleMeta):
    function: Callable = field(default=None)
    name: str = ""
    available_for: list = field(default=["*"], converter=convert_list)
    exclude_from: list = field(default=[], converter=convert_list)
    load: bool = True


__all__ = ["ModuleMeta", "CommandMeta", "RegexMeta", "ScheduleMeta", "HookMeta", "EventMeta"]
