import importlib
import re
import sys
import traceback
from typing import Callable

from core.constants import plugins_path, PrivateAssets
from core.database import reload_db
from core.database.models import ModuleStatus
from core.i18n import load_locale_file
from core.logger import Logger
from core.types import Plugin
from core.types.plugin.component_meta import (
    CommandMeta,
    RegexMeta,
    ScheduleMeta,
    HookMeta,
)


async def load_plugins():
    err_prompt = []
    locale_loaded_err = load_locale_file()
    if locale_loaded_err:
        err_prompt.append("I18N loaded failed:")
        err_prompt.append("\n".join(locale_loaded_err))

    Logger.info("Attempting to load plugins...")

    if not plugins_path.exists():
        Logger.warning("Plugins directory not found.")
        return

    for plugin_folder in plugins_path.iterdir():
        if not plugin_folder.is_dir():
            continue

        plugin_name = plugin_folder.name
        src_path = plugin_folder / "src"

        # 检查是否存在 src 目录以及 __init__.py (确保它是一个合法的包)
        if not src_path.exists() or not (src_path / "__init__.py").exists():
            Logger.debug(f"Skipping {plugin_name}: 'src/__init__.py' not found.")
            continue

        try:
            Logger.debug(f"Loading {plugin_name}...")

            import importlib.util

            spec = importlib.util.spec_from_file_location(plugin_name, str(src_path / "__init__.py"))
            module = importlib.util.module_from_spec(spec)

            # 将该模块注册到 sys.modules 中，防止重复加载并允许相对导入
            sys.modules[plugin_name] = module
            spec.loader.exec_module(module)

            Logger.debug(f"Successfully loaded {plugin_name}!")

            # 3. 尝试加载插件内部的 config.py (位于 src/config.py)
            try:
                config_spec = importlib.util.spec_from_file_location(
                    f"{plugin_name}.config", str(src_path / "config.py")
                )
                if config_spec:
                    config_module = importlib.util.module_from_spec(config_spec)
                    config_spec.loader.exec_module(config_module)
                    Logger.debug(f"Successfully loaded {plugin_name}'s config definition!")
            except Exception:
                Logger.debug(f"Plugin {plugin_name}'s config definition not found or failed, skipped.")

        except Exception:
            errmsg = f"Failed to load {plugin_name}: \n{traceback.format_exc()}"
            Logger.error(errmsg)
            err_prompt.append(errmsg)

        # 4. 插件状态初始化与数据库同步
    await ModuleStatus.init_modules(list(PluginsManager.plugins.keys()))
    for plugin_name, plugin in PluginsManager.plugins.items():
        plugin_status = await ModuleStatus.filter(module_name=plugin_name).first()
        # 注意：原逻辑中 module.load 的判断取决于你 PluginsManager 如何存储模块
        if plugin_status and not plugin_status.load or not getattr(plugin, "load", True):
            plugin._db_load = False

    Logger.success("All plugins loaded.")

    # 5. 错误缓存写入
    loader_cache = PrivateAssets.path / ".cache_loader"
    with open(loader_cache, "w", encoding="utf-8") as open_loader_cache:
        if err_prompt:
            combined_err = "\n".join(err_prompt)
            # 清理 importlib 的冗余回溯信息
            clean_err = re.sub(r'  File "<frozen importlib.*?>", .*?\n', "", combined_err)
            open_loader_cache.write(clean_err)
        else:
            open_loader_cache.write("")

    PluginsManager.refresh()


class PluginsManager:
    plugins: dict[str, Plugin] = {}
    plugins_aliases: dict[str, str] = {}
    plugins_hooks: dict[str, Callable] = {}
    plugins_origin: dict[str, str] = {}
    _deferred_bindings = []

    @classmethod
    def add_plugin(cls, plugin: Plugin, py_module_name: str):
        if plugin.plugin_name not in cls.plugins:
            cls.plugins[plugin.plugin_name] = plugin
            cls.plugins_origin[plugin.plugin_name] = py_module_name
        else:
            raise ValueError(f'Duplicate bind prefix "{plugin.plugin_name}"')

    @classmethod
    def remove_plugins(cls, plugins):
        for plugin in plugins:
            if plugin in cls.plugins:
                cls.plugins.pop(plugin)
                cls.plugins_origin.pop(plugin)
            else:
                raise ValueError(f'Plugin "{plugin}" is not exist.')

    @classmethod
    def refresh_plugins_aliases(cls):
        cls.plugins_aliases.clear()
        for p in cls.plugins:
            plugin = cls.plugins[p]
            if plugin.alias:
                cls.plugins_aliases.update(plugin.alias)

    @classmethod
    def refresh_plugins_hooks(cls):
        cls.plugins_hooks.clear()
        for p in cls.plugins:
            plugin = cls.plugins[p]
            if plugin.hooks_list:
                for hook in plugin.hooks_list.set:
                    hook_name = plugin.plugin_name + (("." + hook.name) if hook.name else "")
                    cls.plugins_hooks.update({hook_name: hook.function})

    @classmethod
    def refresh(cls):
        cls.refresh_plugins_aliases()
        cls.refresh_plugins_hooks()
        cls._return_cache.clear()

    @classmethod
    def search_related_plugin(cls, plugin, include_self=True):
        if plugin in cls.plugins_origin:
            plugins = []
            py_module = cls.return_py_module(plugin)
            for m in cls.plugins_origin:
                if cls.plugins_origin[m].startswith(py_module):
                    plugins.append(m)
            if not include_self:
                plugins.remove(plugin)
            return plugins
        raise ValueError(f'Could not find "{plugin}" in plugins_origin dict')

    @classmethod
    def return_py_module(cls, plugin):
        if plugin in cls.plugins_origin:
            return re.match(r"^plugins(\.[a-zA-Z0-9_]*)?", cls.plugins_origin[plugin]).group()
        return None

    @classmethod
    def bind_to_plugin(
        cls,
        plugin_name: str,
        meta: CommandMeta | RegexMeta | ScheduleMeta | HookMeta,
    ):
        if plugin_name in cls.plugins:
            if isinstance(meta, CommandMeta):
                cls.plugins[plugin_name].command_list.add(meta)
            elif isinstance(meta, RegexMeta):
                cls.plugins[plugin_name].regex_list.add(meta)
            elif isinstance(meta, ScheduleMeta):
                cls.plugins[plugin_name].schedule_list.add(meta)
            elif isinstance(meta, HookMeta):
                cls.plugins[plugin_name].hooks_list.add(meta)

    _return_cache = {}

    @classmethod
    def return_plugins_list(
        cls, target_from: str | None = None, client_name: str | None = None, use_cache: bool = True
    ) -> dict[str, Plugin]:
        if target_from and target_from in cls._return_cache and use_cache:
            return cls._return_cache[target_from]
        plugins = {plugin_name: cls.plugins[plugin_name] for plugin_name in sorted(cls.plugins)}

        if target_from:
            if not client_name:
                if "|" in target_from:
                    client_name = target_from.split("|")[0]
                else:
                    client_name = target_from
            returns = {}
            for p in plugins:
                if isinstance(plugins[p], Plugin):
                    available = plugins[p].available_for
                    exclude = plugins[p].exclude_from
                    if not plugins[p].load:
                        continue
                    if target_from in exclude or client_name in exclude:
                        continue
                    if target_from in available or client_name in available or "*" in available:
                        returns.update({p: plugins[p]})
            cls._return_cache.update({target_from: returns})
            return returns
        return plugins

    @classmethod
    async def load_plugin(cls, plugin_name: str):
        """
        全域加载该机器人模块。
        """
        if plugin_name in cls.plugins:
            cls.plugins[plugin_name]._db_load = True
            await ModuleStatus.set_module_loaded(plugin_name, True)
            return True
        return False

    @classmethod
    async def unload_plugin(cls, plugin_name: str):
        """
        全域卸载该机器人模块。
        """
        if plugin_name in cls.plugins:
            cls.plugins[plugin_name]._db_load = False
            await ModuleStatus.set_module_loaded(plugin_name, False)
            return True
        return False

    @classmethod
    async def reload_plugin(cls, plugin_name: str):
        """
        重载该机器人模块（以及该模块所在文件的其它模块）
        """
        py_module = cls.return_py_module(plugin_name)
        related_plugins = cls.search_related_plugin(plugin_name)

        cls.remove_plugins(related_plugins)
        await ModuleStatus.filter(module_name__in=related_plugins).delete()
        count = cls.reload_py_module(py_module)

        if count > 0 and related_plugins:
            await ModuleStatus.bulk_create([ModuleStatus(plugin_name=m, load=True) for m in related_plugins])
        cls.refresh()
        await reload_db()
        return count > 0, count

    @classmethod
    def reload_py_module(cls, plugin_name: str):
        """
        重载该Python模块
        """
        try:
            Logger.info(f"Reloading {plugin_name} ...")
            module = sys.modules[plugin_name]
            cnt = 0
            loaded_module_list = list(sys.modules.keys())
            for mod in loaded_module_list:
                if mod.startswith(f"{plugin_name}."):
                    cnt += cls.reload_py_module(mod)
            importlib.reload(module)
            Logger.success(f"Successfully reloaded {plugin_name}.")
            return cnt + 1
        except Exception:
            Logger.exception(f"Failed to reload {plugin_name}:")
            return -999
        finally:
            cls.refresh()
