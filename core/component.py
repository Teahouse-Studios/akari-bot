import re
from typing import Union

from apscheduler.triggers.combining import AndTrigger, OrTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from core.elements import Command, RegexCommand, Schedule, StartUp
from core.elements.module.component_meta import *
from core.loader import ModulesManager
from core.parser.args import parse_template


class Bind:
    class Command:
        def __init__(self, bind_prefix):
            self.bind_prefix = bind_prefix

        def handle(self,
                   help_doc: Union[str, list, tuple] = None,
                   *help_docs,
                   options_desc: dict = None,
                   required_admin: bool = False,
                   required_superuser: bool = False,
                   available_for: Union[str, list, tuple] = '*',
                   exclude_from: Union[str, list, tuple] = '',
                   priority: int = 1):
            def decorator(function):
                nonlocal help_doc
                if isinstance(help_doc, str):
                    help_doc = [help_doc]
                if help_docs:
                    help_doc += help_docs
                if help_doc is None:
                    help_doc = []

                ModulesManager.bind_to_module(self.bind_prefix, CommandMeta(function=function,
                                                                            help_doc=parse_template(help_doc),
                                                                            options_desc=options_desc,
                                                                            required_admin=required_admin,
                                                                            required_superuser=required_superuser,
                                                                            available_for=available_for,
                                                                            exclude_from=exclude_from,
                                                                            priority=priority))
                return function

            return decorator

    class Regex:
        def __init__(self, bind_prefix):
            self.bind_prefix = bind_prefix

        def handle(self, pattern: Union[str, re.Pattern], mode: str = "M", flags: re.RegexFlag = 0,
                   show_typing: bool = True, logging: bool = True):
            def decorator(function):
                ModulesManager.bind_to_module(self.bind_prefix, RegexMeta(function=function,
                                                                          pattern=pattern,
                                                                          mode=mode,
                                                                          flags=flags,
                                                                          show_typing=show_typing,
                                                                          logging=logging))
                return function

            return decorator

    class Schedule:
        def __init__(self, bind_prefix):
            self.bind_prefix = bind_prefix

        def handle(self):
            def decorator(function):
                ModulesManager.bind_to_module(self.bind_prefix, ScheduleMeta(function=function))
                return function

            return decorator


def on_command(
    bind_prefix: str,
    alias: Union[str, list, tuple, dict] = None,
    desc: str = None,
    recommend_modules: Union[str, list, tuple] = None,
    developers: Union[str, list, tuple] = None,
    required_admin: bool = False,
    base: bool = False,
    required_superuser: bool = False,
    available_for: Union[str, list, tuple] = '*',
    exclude_from: Union[str, list, tuple] = ''
):
    """

    :param bind_prefix: 绑定的命令前缀。
    :param alias: 此命令的别名。
    同时被用作命令解析，当此项不为空时将会尝试解析其中的语法并储存结果在 MessageSession.parsed_msg 中。
    :param desc: 此命令的简介。
    :param recommend_modules: 推荐打开的其他模块。
    :param developers: 模块作者。
    :param required_admin: 此命令是否需要群聊管理员权限。
    :param base: 将此命令设为基础命令。设为基础命令后此命令将被强制开启。
    :param required_superuser: 将此命令设为机器人的超级管理员才可执行。
    :param available_for: 此命令支持的平台列表。
    :param exclude_from: 此命令排除的平台列表。
    :return: 此类型的模块。
    """
    module = Command(alias=alias,
                     bind_prefix=bind_prefix,
                     desc=desc,
                     recommend_modules=recommend_modules,
                     developers=developers,
                     base=base,
                     required_admin=required_admin,
                     required_superuser=required_superuser,
                     available_for=available_for,
                     exclude_from=exclude_from)
    ModulesManager.add_module(module)
    return Bind.Command(bind_prefix)


def on_regex(
    bind_prefix: str,
    recommend_modules: Union[str, list, tuple] = None,
    alias: Union[str, list, tuple, dict] = None,
    desc: str = None,
    developers: Union[str, list, tuple] = None,
    required_admin: bool = False,
    base: bool = False,
    required_superuser: bool = False,
    available_for: Union[str, list, tuple] = '*',
    exclude_from: Union[str, list, tuple] = ''
):
    """

    :param bind_prefix: 绑定的命令前缀。
    模式所获取到的内容将会储存在 MessageSession.matched_msg 中。
    :param alias: 此命令的别名。
    :param desc: 此命令的简介。
    :param recommend_modules: 推荐打开的其他模块。
    :param developers: 模块作者。
    :param required_admin: 此命令是否需要群聊管理员权限。
    :param base: 将此命令设为基础命令。设为基础命令后此命令将被强制开启。
    :param required_superuser: 将此命令设为机器人的超级管理员才可执行。
    :param available_for: 此命令支持的平台列表。
    :param exclude_from: 此命令排除的平台列表。
    :return: 此类型的模块。
    """

    module = RegexCommand(bind_prefix=bind_prefix,
                          recommend_modules=recommend_modules,
                          alias=alias,
                          desc=desc,
                          developers=developers,
                          required_admin=required_admin,
                          base=base,
                          required_superuser=required_superuser,
                          available_for=available_for,
                          exclude_from=exclude_from
                          )
    ModulesManager.add_module(module)
    return Bind.Regex(bind_prefix)


def on_schedule(
    bind_prefix: str,
    trigger: Union[AndTrigger, OrTrigger, DateTrigger, CronTrigger, IntervalTrigger],
    desc: str = None,
    alias: Union[str, list, tuple, dict] = None,
    recommend_modules: Union[str, list, tuple] = None,
    developers: Union[str, list, tuple] = None,
    required_superuser: bool = False,
    available_for: Union[str, list, tuple] = '*',
    exclude_from: Union[str, list, tuple] = ''
):
    """
    :param bind_prefix: 绑定的命令前缀。
    :param trigger: 此命令的触发器。
    :param alias: 此命令的别名。
    :param desc: 此命令的简介。
    :param recommend_modules: 推荐打开的其他模块。
    :param developers: 模块作者。
    :param required_superuser: 将此命令设为机器人的超级管理员才可执行。
    :param available_for: 此命令支持的平台列表。
    :param exclude_from: 此命令排除的平台列表。
    :return: 此类型的模块。
    """

    def decorator(function):
        module = Schedule(function=function,
                          trigger=trigger,
                          bind_prefix=bind_prefix,
                          desc=desc,
                          alias=alias,
                          recommend_modules=recommend_modules,
                          developers=developers,
                          required_superuser=required_superuser,
                          available_for=available_for,
                          exclude_from=exclude_from)
        ModulesManager.add_module(module)
        return module

    return decorator


def on_startup(
    bind_prefix: str,
    desc: str = None,
    alias: Union[str, list, tuple, dict] = None,
    recommend_modules: Union[str, list, tuple] = None,
    developers: Union[str, list, tuple] = None,
    required_superuser: bool = False,
    available_for: Union[str, list, tuple] = '*',
    exclude_from: Union[str, list, tuple] = ''
):
    """

    :param bind_prefix: 绑定的命令前缀。
    :param alias: 此命令的别名。
    :param desc: 此命令的简介。
    :param recommend_modules: 推荐打开的其他模块。
    :param developers: 模块作者。
    :param required_superuser: 将此命令设为机器人的超级管理员才可执行。
    :param available_for: 此命令支持的平台列表。
    :param exclude_from: 此命令排除的平台列表。
    :return: 此类型的模块。
    """

    def decorator(function):
        module = StartUp(function=function,
                         bind_prefix=bind_prefix,
                         desc=desc,
                         alias=alias,
                         recommend_modules=recommend_modules,
                         developers=developers,
                         required_superuser=required_superuser,
                         available_for=available_for,
                         exclude_from=exclude_from
                         )
        ModulesManager.add_module(module)
        return module

    return decorator
