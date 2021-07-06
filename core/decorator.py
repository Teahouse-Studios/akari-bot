from typing import Union, Coroutine, Optional
from .elements import Plugin
from .loader import PluginManager

def command(
    name: str,
    alias: Union[str, list, None] = None,
    help: Union[str, None] = None,
    self_process: bool = False,
    autorun: bool = False
):
    def decorator(func):
        function = func
        plugin = Plugin(function=func, name=name)
        PluginManager.add_plugin(plugin)
    return decorator