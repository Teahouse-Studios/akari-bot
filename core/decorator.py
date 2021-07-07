from typing import Union, Coroutine, Optional
from .elements import Plugin
from .loader import PluginManager

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
        plugin = Plugin(function,
                        bind_prefix,
                        alias,
                        help_doc,
                        need_self_process,
                        is_admin_function,
                        is_base_function,
                        is_superuser_function,
                        autorun)
        print(Plugin)
        PluginManager.add_plugin(plugin)
    return decorator