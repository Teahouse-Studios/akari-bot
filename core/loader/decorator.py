from core.elements import Module
from core.loader import ModulesManager


def command(
        bind_prefix,
        alias=None,
        help_doc=None,
        need_self_process=False,
        need_admin=False,
        is_base_function=False,
        need_superuser=False,
        is_regex_function=False,
        autorun=False,
        desc=None
):
    def decorator(function):
        plugin = Module(function=function,
                        bind_prefix=bind_prefix,
                        alias=alias,
                        help_doc=help_doc,
                        need_self_process=need_self_process,
                        need_admin=need_admin,
                        is_base_function=is_base_function,
                        need_superuser=need_superuser,
                        is_regex_function=is_regex_function,
                        autorun=autorun,
                        desc=desc)
        ModulesManager.add_module(plugin)

    return decorator
