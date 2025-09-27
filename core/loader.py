import importlib
import pkgutil
import re
import sys
import traceback
from typing import Dict, Optional, Union, Callable

from core.constants import PrivateAssets
from core.database import reload_db
from core.database.models import ModuleStatus
from core.i18n import load_locale_file
from core.logger import Logger
from core.types import Module
from core.types.module.component_meta import (
    CommandMeta,
    RegexMeta,
    ScheduleMeta,
    HookMeta,
)


async def load_modules():
    import modules

    err_prompt = []
    locale_loaded_err = load_locale_file()
    if locale_loaded_err:
        err_prompt.append("I18N loaded failed:")
        err_prompt.append("\n".join(locale_loaded_err))

    Logger.info("Attempting to load modules...")

    for subm in pkgutil.iter_modules(modules.__path__):
        module_py_name = f"{modules.__name__}.{subm.name}"
        try:
            Logger.debug(f"Loading {module_py_name}...")

            importlib.import_module(module_py_name)
            Logger.debug(f"Successfully loaded {module_py_name}!")

            try:
                importlib.import_module(f"{module_py_name}.config")
                Logger.debug(f"Successfully loaded {module_py_name}'s config definition!")
            except ModuleNotFoundError:
                Logger.debug(f"Module {module_py_name}'s config definition not found, skipped.")

        except Exception:
            errmsg = f"Failed to load {module_py_name}: \n{traceback.format_exc()}"
            Logger.error(errmsg)
            err_prompt.append(errmsg)

    await ModuleStatus.init_modules(list(ModulesManager.modules.keys()))
    for module_name, module in ModulesManager.modules.items():
        module_status = await ModuleStatus.filter(module_name=module_name).first()
        if module_status and not module_status.load or not module.load:
            module._db_load = False

    Logger.success("All modules loaded.")

    loader_cache = PrivateAssets.path / ".cache_loader"
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
    _deferred_bindings = []

    @classmethod
    def add_module(cls, module: Module, py_module_name: str):
        if module.module_name not in cls.modules:
            cls.modules[module.module_name] = module
            cls.modules_origin[module.module_name] = py_module_name
        else:
            raise ValueError(f'Duplicate bind prefix "{module.module_name}"')

    @classmethod
    def remove_modules(cls, modules):
        for module in modules:
            if module in cls.modules:
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
                    hook_name = module.module_name + (
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
        module_name: str,
        meta: Union[CommandMeta, RegexMeta, ScheduleMeta, HookMeta],
    ):
        if module_name in cls.modules:
            if isinstance(meta, CommandMeta):
                cls.modules[module_name].command_list.add(meta)
            elif isinstance(meta, RegexMeta):
                cls.modules[module_name].regex_list.add(meta)
            elif isinstance(meta, ScheduleMeta):
                cls.modules[module_name].schedule_list.add(meta)
            elif isinstance(meta, HookMeta):
                cls.modules[module_name].hooks_list.add(meta)

    _return_cache = {}

    @classmethod
    def return_modules_list(cls, target_from: Optional[str] = None,
                            client_name: Optional[str] = None, use_cache: bool = True) -> Dict[str, Module]:
        if target_from and target_from in cls._return_cache and use_cache:
            return cls._return_cache[target_from]
        modules = {
            module_name: cls.modules[module_name] for module_name in sorted(cls.modules)
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
    async def load_module(cls, module_name: str):
        """
        全域加载该机器人模块。
        """
        if module_name in cls.modules:
            cls.modules[module_name]._db_load = True
            await ModuleStatus.set_module_loaded(module_name, True)
            return True
        return False

    @classmethod
    async def unload_module(cls, module_name: str):
        """
        全域卸载该机器人模块。
        """
        if module_name in cls.modules:
            cls.modules[module_name]._db_load = False
            await ModuleStatus.set_module_loaded(module_name, False)
            return True
        return False

    @classmethod
    async def reload_module(cls, module_name: str):
        """
        重载该机器人模块（以及该模块所在文件的其它模块）
        """
        py_module = cls.return_py_module(module_name)
        related_modules = cls.search_related_module(module_name)

        cls.remove_modules(related_modules)
        await ModuleStatus.filter(module_name__in=related_modules).delete()
        count = cls.reload_py_module(py_module)

        if count > 0 and related_modules:
            await ModuleStatus.bulk_create(
                [ModuleStatus(module_name=m, load=True) for m in related_modules]
            )
        cls.refresh()
        await reload_db()
        return count > 0, count

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
            return cnt + 1
        except Exception:
            Logger.exception(f"Failed to reload {module_name}:")
            return -999
        finally:
            cls.refresh()
