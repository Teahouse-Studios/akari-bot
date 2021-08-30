from core.elements import Command, Option, Schedule
from core.loader import ModulesManager

from apscheduler.triggers.combining import AndTrigger, OrTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger


def command(
        bind_prefix: str,
        alias: [str, list, tuple] = None,
        help_doc: [str, list, tuple] = None,
        desc: str = None,
        need_self_process: bool = False,
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
                         desc=desc,
                         is_base_function=is_base_function,
                         is_regex_function=is_regex_function,
                         need_admin=need_admin,
                         need_self_process=need_self_process,
                         need_superuser=need_superuser,
                         autorun=autorun)
        ModulesManager.add_module(module)
        return module

    return decorator


def option(
        bind_prefix: str,
        desc: str = None,
        help_doc: [str, list, tuple] = None,
        alias: [str, list, tuple] = None,
        need_superuser: bool = False,
        need_admin: bool = False
):
    def decorator(function):
        module = Option(bind_prefix=bind_prefix,
                        desc=desc,
                        help_doc=help_doc,
                        alias=alias,
                        need_superuser=need_superuser,
                        need_admin=need_admin)
        ModulesManager.add_module(module)
        return module

    return decorator


def schedule(
        bind_prefix: str,
        trigger: [AndTrigger, OrTrigger, DateTrigger, CronTrigger, IntervalTrigger],
        desc: str = None,
        help_doc: [str, list, tuple] = None,
        alias: [str, list, tuple] = None,
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
                          need_superuser=need_superuser,
                          need_admin=need_admin)
        ModulesManager.add_module(module)
        return module

    return decorator
