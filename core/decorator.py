from core.elements import Module
from .loader import ModulesManager

def command(
    bind_prefix,
    alias=None,
    help_doc='',
    need_self_process=False,
    is_admin_function=False,
    is_base_function=False,
    is_superuser_function=False,
    autorun=False
):
    def decorator(function):
        plugin = Module(function,
                        bind_prefix,
                        alias,
                        help_doc,
                        need_self_process,
                        is_admin_function,
                        is_base_function,
                        is_superuser_function,
                        autorun)
        ModulesManager.add_module(plugin)
    return decorator