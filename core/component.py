import inspect
import re
from typing import Union, overload

from apscheduler.triggers.combining import AndTrigger, OrTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from core.loader import ModulesManager
from core.parser.args import parse_template
from core.types import Module
from core.types.module.component_meta import *


class Bind:
    class Module:
        def __init__(self, bind_prefix: str):
            self.bind_prefix = bind_prefix

        def command(self,
                    help_doc: Union[str, list, tuple] = None,
                    *help_docs,
                    options_desc: dict = None,
                    required_admin: bool = False,
                    required_superuser: bool = False,
                    required_base_superuser: bool = False,
                    available_for: Union[str, list, tuple] = '*',
                    exclude_from: Union[str, list, tuple] = '',
                    priority: int = 1):
            def decorator(function):
                nonlocal help_doc
                if isinstance(help_doc, str):
                    help_doc = [help_doc]
                if help_docs:
                    help_doc += help_docs
                if not help_doc:
                    help_doc = []

                ModulesManager.bind_to_module(
                    self.bind_prefix,
                    CommandMeta(
                        function=function,
                        help_doc=parse_template(help_doc),
                        options_desc=options_desc,
                        required_admin=required_admin,
                        required_superuser=required_superuser,
                        required_base_superuser=required_base_superuser,
                        available_for=available_for,
                        exclude_from=exclude_from,
                        priority=priority))
                return function

            return decorator

        def regex(self, pattern: Union[str, re.Pattern], mode: str = "M", flags: re.RegexFlag = 0,
                  desc: str = None,
                  required_admin: bool = False,
                  required_superuser: bool = False,
                  required_base_superuser: bool = False,
                  available_for: Union[str, list, tuple] = '*',
                  exclude_from: Union[str, list, tuple] = '',
                  show_typing: bool = True, logging: bool = True):
            def decorator(function):
                ModulesManager.bind_to_module(
                    self.bind_prefix,
                    RegexMeta(
                        function=function,
                        pattern=pattern,
                        mode=mode,
                        flags=flags,
                        desc=desc,
                        required_admin=required_admin,
                        required_superuser=required_superuser,
                        required_base_superuser=required_base_superuser,
                        available_for=available_for,
                        exclude_from=exclude_from,
                        show_typing=show_typing,
                        logging=logging))
                return function

            return decorator

        def schedule(self, trigger: Union[AndTrigger, OrTrigger, DateTrigger, CronTrigger, IntervalTrigger]):
            def decorator(function):
                ModulesManager.bind_to_module(self.bind_prefix, ScheduleMeta(function=function, trigger=trigger))
                return function

            return decorator

        def hook(self, name: str = None):
            def decorator(function):
                ModulesManager.bind_to_module(self.bind_prefix, HookMeta(function=function, name=name))
                return function

            return decorator

        on_command = command
        on_regex = regex
        on_schedule = schedule
        on_hook = hook

        @overload
        def handle(self,
                   help_doc: Union[str, list, tuple] = None,
                   *help_docs,
                   options_desc: dict = None,
                   required_admin: bool = False,
                   required_superuser: bool = False,
                   required_base_superuser: bool = False,
                   available_for: Union[str, list, tuple] = '*',
                   exclude_from: Union[str, list, tuple] = '',
                   priority: int = 1):
            ...

        @overload
        def handle(self, pattern: Union[str, re.Pattern], mode: str = "M", flags: re.RegexFlag = 0,
                   desc: str = None,
                   required_admin: bool = False,
                   required_superuser: bool = False,
                   required_base_superuser: bool = False,
                   available_for: Union[str, list, tuple] = '*',
                   exclude_from: Union[str, list, tuple] = '',
                   show_typing: bool = True, logging: bool = True):
            ...

        @overload
        def handle(self, trigger: Union[AndTrigger, OrTrigger, DateTrigger, CronTrigger, IntervalTrigger]):
            ...

        def handle(self, *args, **kwargs):
            first_key = args[0] if args else (kwargs[list(kwargs.keys())[0]] if kwargs else None)
            if isinstance(first_key, re.Pattern):
                return self.regex(*args, **kwargs)
            elif isinstance(first_key, (AndTrigger, OrTrigger, DateTrigger, CronTrigger, IntervalTrigger)):
                return self.schedule(*args, **kwargs)
            return self.command(*args, **kwargs)


def module(
    bind_prefix: str,
    alias: Union[str, list, tuple, dict, None] = None,
    desc: str | None = None,
    recommend_modules: Union[str, list, tuple, None] = None,
    developers: Union[str, list, tuple, None] = None,
    required_admin: bool = False,
    base: bool = False,
    required_superuser: bool = False,
    required_base_superuser: bool = False,
    available_for: Union[str, list, tuple] = '*',
    exclude_from: Union[str, list, tuple] = '',
    support_languages: Union[str, list, tuple, None] = None
):
    """

    :param bind_prefix: 绑定的命令前缀。
    :param alias: 此命令的别名。
    同时被用作命令解析，当此项不为空时将会尝试解析其中的语法并储存结果在 MessageSession.parsed_msg 中。
    :param desc: 此命令的简介。
    :param recommend_modules: 推荐打开的其他模块。
    :param developers: 模块作者。
    :param required_admin: 此命令是否需要群组管理员权限。
    :param base: 将此命令设为基础命令。设为基础命令后此命令将被强制开启。
    :param required_superuser: 将此命令设为机器人的超级管理员才可执行。
    :param required_base_superuser: 将此命令设为机器人的基础超级管理员才可执行。
    :param available_for: 此命令支持的平台列表。
    :param exclude_from: 此命令排除的平台列表。
    :return: 此类型的模块。
    """
    module = Module(alias=alias,
                    bind_prefix=bind_prefix,
                    desc=desc,
                    recommend_modules=recommend_modules,
                    developers=developers,
                    base=base,
                    required_admin=required_admin,
                    required_superuser=required_superuser,
                    required_base_superuser=required_base_superuser,
                    available_for=available_for,
                    exclude_from=exclude_from,
                    support_languages=support_languages)
    frame = inspect.currentframe()
    ModulesManager.add_module(module, frame.f_back.f_globals["__name__"])
    return Bind.Module(bind_prefix)
