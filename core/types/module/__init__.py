from copy import deepcopy

from apscheduler.triggers.combining import AndTrigger, OrTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from attrs import define, field, Converter

from core.utils.func import convert_list
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
    regex: bool = False
    event: bool = False
    required_superuser: bool = False
    required_base_superuser: bool = False
    required_bot_permissions: list = field(factory=list, converter=convert_list)
    suppress_invalid_prompt: bool = False
    command_list: CommandMatches = field(factory=CommandMatches.init)
    regex_list: RegexMatches = field(factory=RegexMatches.init)
    schedule_list: ScheduleMatches = field(factory=ScheduleMatches.init)
    hooks_list: HookMatches = field(factory=HookMatches.init)
    events_list: EventMatches = field(factory=EventMatches.init)
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
            "regex": self.regex,
            "event": self.event,
            "required_superuser": self.required_superuser,
            "required_base_superuser": self.required_base_superuser,
            "required_bot_permissions": self.required_bot_permissions,
            "suppress_invalid_prompt": self.suppress_invalid_prompt,
            "commands": len(self.command_list.set),
            "regexp": len(self.regex_list.set),
            "events": len(self.events_list.set),
            "_py_module_name": self._py_module_name,
            "_db_load": self._db_load,
        }

    def unsupported_reason(self, session_info) -> str | None:
        """判断该模块在给定会话中是否受平台能力或权限所限。

        :param session_info: 会话信息，须具备 support_rss 与 read_all_messages 两项标志。
        :return: 受限时返回成因（``rss``、``regex`` 或 ``event``），不受限时返回 None。
        """
        if self.rss and not session_info.support_rss:
            return "rss"
        if self.regex and not session_info.read_all_messages:
            return "regex"
        if self.event and not session_info.read_all_messages:
            return "event"
        return None

    def bot_permissions_for_enable(self) -> list[str]:
        """Return native bot permissions required before enabling this module."""
        permissions = list(self.required_bot_permissions or [])
        if self.event or self.regex:
            permissions.append("can_read_all_messages")
        if self.rss:
            permissions.append("can_send_proactive_messages")
        return list(dict.fromkeys(permissions))

    def unsupported_bot_permissions(self, bot_state) -> list[str]:
        """Return permissions explicitly known to be unavailable in ``bot_state``."""
        if bot_state is None:
            return []
        missing = []
        for permission in self.bot_permissions_for_enable():
            value = (
                bot_state.has_permission(permission.removeprefix("permissions."))
                if permission.startswith("permissions.")
                else getattr(bot_state, permission, None)
            )
            if value is False:
                missing.append(permission)
        return missing


__all__ = [
    "Module",
    "AndTrigger",
    "OrTrigger",
    "DateTrigger",
    "CronTrigger",
    "IntervalTrigger",
]
