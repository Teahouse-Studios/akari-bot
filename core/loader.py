import importlib
import os
import pkgutil
import re
import sys
import traceback
from typing import Dict, Optional, Union, Callable

from core.config import CFGManager
from core.constants import PrivateAssets
from core.database import reload_db
from core.i18n import load_locale_file
from core.logger import Logger
from core.types import Module
from core.types.module.component_meta import (
    CommandMeta,
    RegexMeta,
    ScheduleMeta,
    HookMeta,
)

current_unloaded_modules = []
err_modules = []


def load_modules():
    import modules
    unloaded_modules = CFGManager.get("unloaded_modules", [])
    err_prompt = []
    locale_loaded_err = load_locale_file()
    if locale_loaded_err:
        err_prompt.append("I18N loaded failed:")
        err_prompt.append("\n".join(locale_loaded_err))

    Logger.info("Attempting to load modules...")
    for subm in pkgutil.iter_modules(modules.__path__):
        submodule_name = modules.__name__ + "." + subm.name
        try:
            Logger.debug(f"Loading {submodule_name}...")
            if subm.name in unloaded_modules:
                Logger.warning(f"Skipped {submodule_name}!")
                current_unloaded_modules.append(subm.name)
                continue
            importlib.import_module(submodule_name)
            Logger.debug(f"Successfully loaded {submodule_name}!")
            try:
                importlib.import_module(submodule_name + ".config")
                Logger.debug(f"Successfully loaded {submodule_name}'s config definition!")
            except ModuleNotFoundError:
                Logger.debug(f"Module {submodule_name}'s config definition not found, skipped.")
        except Exception:
            errmsg = f"Failed to load {submodule_name}: \n{traceback.format_exc()}"
            Logger.error(errmsg)
            err_prompt.append(errmsg)
            err_modules.append(subm.name)
    Logger.success("All modules loaded.")
    loader_cache = os.path.join(PrivateAssets.path, ".cache_loader")
    with open(loader_cache, "w") as open_loader_cache:
        if err_prompt:
            err_prompt = re.sub(
                r"  File \"<frozen importlib.*?>\", .*?\n", "", "\n".join(err_prompt)
            )
            open_loader_cache.write(err_prompt)
        else:
            open_loader_cache.write("")

    ModulesManager.refresh()


class ModulesManager:
    modules: Dict[str, Module] = {}
    modules_aliases: Dict[str, str] = {}
    modules_hooks: Dict[str, Callable] = {}
    modules_origin: Dict[str, str] = {}

    @classmethod
    def add_module(cls, module: Module, py_module_name: str):
        if module.bind_prefix not in ModulesManager.modules:
            cls.modules.update({module.bind_prefix: module})
            cls.modules_origin.update({module.bind_prefix: py_module_name})
        else:
            raise ValueError(f"Duplicate bind prefix \"{module.bind_prefix}\"")

    @classmethod
    def remove_modules(cls, modules):
        for module in modules:
            if module in cls.modules:
                Logger.info(f"Removing... {module}")
                cls.modules.pop(module)
                cls.modules_origin.pop(module)
            else:
                raise ValueError(f"Module \"{module}\" is not exist.")

    @classmethod
    def refresh_modules_aliases(cls):
        cls.modules_aliases.clear()
        for m in cls.modules:
            module = cls.modules[m]
            if module.alias:
                cls.modules_aliases.update(module.alias)

    @classmethod
    def refresh_modules_hooks(cls):
        cls.modules_hooks.clear()
        for m in cls.modules:
            module = cls.modules[m]
            if module.hooks_list:
                for hook in module.hooks_list.set:
                    hook_name = module.bind_prefix + (
                        ("." + hook.name) if hook.name else ""
                    )
                    cls.modules_hooks.update({hook_name: hook.function})

    @classmethod
    def refresh(cls):
        cls.refresh_modules_aliases()
        cls.refresh_modules_hooks()
        cls._return_cache.clear()

    @classmethod
    def search_related_module(cls, module, include_self=True):
        if module in cls.modules_origin:
            modules = []
            py_module = cls.return_py_module(module)
            for m in cls.modules_origin:
                if cls.modules_origin[m].startswith(py_module):
                    modules.append(m)
            if not include_self:
                modules.remove(module)
            return modules
        raise ValueError(f"Could not find \"{module}\" in modules_origin dict")

    @classmethod
    def return_py_module(cls, module):
        if module in cls.modules_origin:
            return re.match(
                r"^modules(\.[a-zA-Z0-9_]*)?", cls.modules_origin[module]
            ).group()
        return None

    @classmethod
    def bind_to_module(
        cls,
        bind_prefix: str,
        meta: Union[CommandMeta, RegexMeta, ScheduleMeta, HookMeta],
    ):
        if bind_prefix in cls.modules:
            if isinstance(meta, CommandMeta):
                cls.modules[bind_prefix].command_list.add(meta)
            elif isinstance(meta, RegexMeta):
                cls.modules[bind_prefix].regex_list.add(meta)
            elif isinstance(meta, ScheduleMeta):
                cls.modules[bind_prefix].schedule_list.add(meta)
            elif isinstance(meta, HookMeta):
                cls.modules[bind_prefix].hooks_list.add(meta)

    _return_cache = {}

    @classmethod
    def return_modules_list(cls, target_from: Optional[str] = None,
                            client_name: Optional[str] = None) -> Dict[str, Module]:
        if target_from and target_from in cls._return_cache:
            return cls._return_cache[target_from]
        modules = {
            bind_prefix: cls.modules[bind_prefix] for bind_prefix in sorted(cls.modules)
        }

        if target_from:
            if not client_name:
                if "|" in target_from:
                    client_name = target_from.split("|")[0]
                else:
                    client_name = target_from
            returns = {}
            for m in modules:
                if isinstance(modules[m], Module):
                    available = modules[m].available_for
                    exclude = modules[m].exclude_from
                    if not modules[m].load:
                        continue
                    if target_from in exclude or client_name in exclude:
                        continue
                    if target_from in available or client_name in available or "*" in available:
                        returns.update({m: modules[m]})
            cls._return_cache.update({target_from: returns})
            return returns
        return modules

    @classmethod
    async def reload_module(cls, module_name: str):
        """
        重载该机器人模块（以及该模块所在文件的其它模块）
        """
        py_module = cls.return_py_module(module_name)
        unbind_modules = cls.search_related_module(module_name)
        cls.remove_modules(unbind_modules)
        cls.reload_py_module(py_module)
        cls.refresh()
        await reload_db()
        return True

    @classmethod
    async def load_module(cls, module_name: str):
        """
        加载该机器人模块（以及该模块所在文件的其它模块）
        """
        if module_name not in current_unloaded_modules:
            return False
        modules = "modules." + module_name
        if modules in sys.modules:
            cls.reload_py_module(modules)
            current_unloaded_modules.remove(module_name)
        else:
            try:
                importlib.import_module(modules)
                Logger.success(f"Succeeded loaded modules.{module_name}!")
                if module_name in err_modules:
                    err_modules.remove(module_name)
                current_unloaded_modules.remove(module_name)
            except Exception:
                Logger.exception(f"Failed to load modules.{module_name}: ")
                if module_name not in err_modules:
                    err_modules.append(module_name)
                return False
        cls.refresh()
        await reload_db([modules])
        return True

    @classmethod
    async def unload_module(cls, module_name: str):
        """
        卸载该机器人模块（以及该模块所在文件的其它模块）
        """
        unbind_modules = cls.search_related_module(module_name)
        cls.remove_modules(unbind_modules)
        cls.refresh()
        current_unloaded_modules.append(module_name)
        await reload_db()
        return True

    @classmethod
    def reload_py_module(cls, module_name: str):
        """
        重载该Python模块
        """
        try:
            Logger.info(f"Reloading {module_name} ...")
            module = sys.modules[module_name]
            cnt = 0
            loaded_module_list = list(sys.modules.keys())
            for mod in loaded_module_list:
                if mod.startswith(f"{module_name}."):
                    cnt += cls.reload_py_module(mod)
            importlib.reload(module)
            Logger.success(f"Successfully reloaded {module_name}.")
            if (m := re.match(r"^modules(\.[a-zA-Z0-9_]*)?", module_name)) and m.group(
                1
            ) in err_modules:
                err_modules.remove(m.group(1))
            return cnt + 1
        except Exception:
            Logger.exception(f"Failed to reload {module_name}:")
            if (m := re.match(r"^modules(\.[a-zA-Z0-9_]*)?", module_name)) and m.group(
                1
            ) not in err_modules:
                err_modules.append(m.group(1))
            return -999
        finally:
            cls.refresh()
