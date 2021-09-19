from apscheduler.triggers.combining import AndTrigger, OrTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from core.elements import Command, Option, Schedule
from core.loader import ModulesManager

from typing import Union


def command(
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
        is_regex_function: bool = False,
        autorun: bool = False
):
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
                         is_regex_function=is_regex_function,
                         need_admin=need_admin,
                         need_superuser=need_superuser,
                         autorun=autorun)
        ModulesManager.add_module(module)
        return module

    return decorator


def option(
        bind_prefix: str,
        desc: str = None,
        help_doc: Union[str, list, tuple] = None,
        alias: Union[str, list, tuple, dict] = None,
        recommend_modules: Union[str, list, tuple] = None,
        developers: Union[str, list, tuple] = None,
        need_superuser: bool = False,
        need_admin: bool = False
):
    def decorator(function):
        module = Option(bind_prefix=bind_prefix,
                        desc=desc,
                        help_doc=help_doc,
                        alias=alias,
                        recommend_modules=recommend_modules,
                        developers=developers,
                        need_superuser=need_superuser,
                        need_admin=need_admin)
        ModulesManager.add_module(module)
        return module

    return decorator


def schedule(
        bind_prefix: str,
        trigger: Union[AndTrigger, OrTrigger, DateTrigger, CronTrigger, IntervalTrigger],
        desc: str = None,
        help_doc: Union[str, list, tuple] = None,
        alias: Union[str, list, tuple, dict] = None,
        recommend_modules: Union[str, list, tuple] = None,
        developers: Union[str, list, tuple] = None,
        need_superuser: bool = False,
        need_admin: bool = False
):
    def decorator(function):
        module = Schedule(function=function,
                          trigger=trigger,
                          bind_prefix=bind_prefix,
                          desc=desc,
                          help_doc=help_doc,
                          alias=alias,
                          recommend_modules=recommend_modules,
                          developers=developers,
                          need_superuser=need_superuser,
                          need_admin=need_admin)
        ModulesManager.add_module(module)
        return module

    return decorator
