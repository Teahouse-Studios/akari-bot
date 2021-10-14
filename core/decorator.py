import re
from typing import Union

from apscheduler.triggers.combining import AndTrigger, OrTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from core.elements import Command, RegexCommand, Option, Schedule, StartUp
from core.loader import ModulesManager


def on_command(
        bind_prefix: str,
        alias: Union[str, list, tuple, dict] = None,
        help_doc: Union[str, list, tuple] = None,
        allowed_none: bool = True,
        desc: str = None,
        recommend_modules: Union[str, list, tuple] = None,
        developers: Union[str, list, tuple] = None,
        need_admin: bool = False,
        is_base_function: bool = False,
        need_superuser: bool = False,
        autorun: bool = False
):
    """

    :param bind_prefix: 绑定的命令前缀。
    :param alias: 此命令的别名。
    :param help_doc: 此命令的帮助文档，
    同时被用作命令解析，当此项不为空时将会尝试解析其中的语法并储存结果在 MessageSession.parsed_msg 中。
    :param allowed_none: 是否允许命令解析为 None，设为 False 后如果遇到非法命令语法时将直接提醒语法错误。
    :param desc: 此命令的简介。
    :param recommend_modules: 推荐打开的其他模块。
    :param developers: 模块作者。
    :param need_admin: 此命令是否需要群聊管理员权限。
    :param is_base_function: 将此命令设为基础命令。设为基础命令后此命令将被强制开启。
    :param need_superuser: 将此命令设为机器人的超级管理员才可执行。
    :param autorun: 将此命令设为自动启动类型，设为自动启动类型后将会在机器人运行时自动运行，同时禁用命令处理功能。
    :return: 此类型的模块。
    """

    def decorator(function):
        module = Command(function=function,
                         alias=alias,
                         bind_prefix=bind_prefix,
                         help_doc=help_doc,
                         allowed_none=allowed_none,
                         desc=desc,
                         recommend_modules=recommend_modules,
                         developers=developers,
                         is_base_function=is_base_function,
                         need_admin=need_admin,
                         need_superuser=need_superuser,
                         autorun=autorun)
        ModulesManager.add_module(module)
        return module

    return decorator


def on_regex(
        bind_prefix: str,
        pattern: str,
        mode: str = "M",
        flags: re.RegexFlag = 0,
        recommend_modules: Union[str, list, tuple] = None,
        alias: Union[str, list, tuple, dict] = None,
        desc: str = None,
        developers: Union[str, list, tuple] = None,
        need_admin: bool = False,
        is_base_function: bool = False,
        need_superuser: bool = False):
    """

    :param bind_prefix: 绑定的命令前缀。
    :param pattern: 正则表达式。
    :param flags: 正则表达式参数
    :param mode: 正则表达式模式，为 "m" 时为 Match模式， 为 "a" 时为 Find_all 模式。
    模式所获取到的内容将会储存在 MessageSession.matched_msg 中。
    :param alias: 此命令的别名。
    :param desc: 此命令的简介。
    :param recommend_modules: 推荐打开的其他模块。
    :param developers: 模块作者。
    :param need_admin: 此命令是否需要群聊管理员权限。
    :param is_base_function: 将此命令设为基础命令。设为基础命令后此命令将被强制开启。
    :param need_superuser: 将此命令设为机器人的超级管理员才可执行。
    :return: 此类型的模块。
    """

    def decorator(function):
        module = RegexCommand(function=function,
                              bind_prefix=bind_prefix,
                              pattern=pattern,
                              flags=flags,
                              mode=mode,
                              recommend_modules=recommend_modules,
                              alias=alias,
                              desc=desc,
                              developers=developers,
                              need_admin=need_admin,
                              is_base_function=is_base_function,
                              need_superuser=need_superuser,
                              )
        ModulesManager.add_module(module)
        return module

    return decorator


def on_option(
        bind_prefix: str,
        desc: str = None,
        alias: Union[str, list, tuple, dict] = None,
        recommend_modules: Union[str, list, tuple] = None,
        developers: Union[str, list, tuple] = None,
        need_superuser: bool = False,
        need_admin: bool = False
):
    """

    :param bind_prefix: 绑定的命令前缀。
    :param alias: 此命令的别名。
    :param desc: 此命令的简介。
    :param recommend_modules: 推荐打开的其他模块。
    :param developers: 模块作者。
    :param need_admin: 此命令是否需要群聊管理员权限。
    :param need_superuser: 将此命令设为机器人的超级管理员才可执行。
    :return: 此类型的模块。
    """

    def decorator(function):
        module = Option(bind_prefix=bind_prefix,
                        desc=desc,
                        alias=alias,
                        recommend_modules=recommend_modules,
                        developers=developers,
                        need_superuser=need_superuser,
                        need_admin=need_admin)
        ModulesManager.add_module(module)
        return module

    return decorator


def on_schedule(
        bind_prefix: str,
        trigger: Union[AndTrigger, OrTrigger, DateTrigger, CronTrigger, IntervalTrigger],
        desc: str = None,
        alias: Union[str, list, tuple, dict] = None,
        recommend_modules: Union[str, list, tuple] = None,
        developers: Union[str, list, tuple] = None,
        need_superuser: bool = False,
):
    """

    :param bind_prefix: 绑定的命令前缀。
    :param trigger: 此命令的触发器。
    :param alias: 此命令的别名。
    :param desc: 此命令的简介。
    :param recommend_modules: 推荐打开的其他模块。
    :param developers: 模块作者。
    :param need_superuser: 将此命令设为机器人的超级管理员才可执行。
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
                          need_superuser=need_superuser)
        ModulesManager.add_module(module)
        return module

    return decorator


def on_startup(
        bind_prefix: str,
        desc: str = None,
        alias: Union[str, list, tuple, dict] = None,
        recommend_modules: Union[str, list, tuple] = None,
        developers: Union[str, list, tuple] = None,
        need_superuser: bool = False,
):
    """

    :param bind_prefix: 绑定的命令前缀。
    :param alias: 此命令的别名。
    :param desc: 此命令的简介。
    :param recommend_modules: 推荐打开的其他模块。
    :param developers: 模块作者。
    :param need_superuser: 将此命令设为机器人的超级管理员才可执行。
    :return: 此类型的模块。
    """

    def decorator(function):
        module = StartUp(function=function,
                         bind_prefix=bind_prefix,
                         desc=desc,
                         alias=alias,
                         recommend_modules=recommend_modules,
                         developers=developers,
                         need_superuser=need_superuser)
        ModulesManager.add_module(module)
        return module

    return decorator
