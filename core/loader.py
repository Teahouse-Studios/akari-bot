import importlib
import importlib.util
import asyncio
import ast
import hashlib
import inspect
import pkgutil
import re
import sys
import traceback
from pathlib import Path
from typing import Callable

from core.builtins.session.info import EventInfo
from core.config import CFGManager
from core.constants import PrivateAssets, all_locales_path, lang_list
from core.database import reload_db
from core.database.base import DBModel
from core.database.models import ModuleStatus
from core.i18n import build_locale_snapshot
from core.logger import Logger
from core.module_runtime import ModuleRuntimeManager
from core.scheduler import SchedulerLifecycle
from core.types import Module
from core.types.module.component_meta import (
    CommandMeta,
    RegexMeta,
    ScheduleMeta,
    HookMeta,
    EventMeta,
)


async def load_modules():
    import modules

    err_prompt = []

    Logger.info("Attempting to load modules...")

    for subm in pkgutil.iter_modules(modules.__path__):
        module_py_name = f"{modules.__name__}.{subm.name}"
        old_module_names = ModulesManager._module_names_for_py_module(module_py_name)
        old_modules = {name: ModulesManager.modules[name] for name in old_module_names}
        old_origins = {name: ModulesManager.modules_origin[name] for name in old_module_names}
        try:
            Logger.debug(f"Loading {module_py_name}...")

            importlib.import_module(module_py_name)
            Logger.debug(f"Successfully loaded {module_py_name}!")

            config_module_name = f"{module_py_name}.config"
            try:
                importlib.import_module(config_module_name)
                Logger.debug(f"Successfully loaded {module_py_name}'s config definition!")
            except ModuleNotFoundError as e:
                # 只忽略配置模块本身不存在。配置文件内部缺少依赖同样表现为
                # ModuleNotFoundError，若一概吞掉会让模块在缺少必要配置时半加载。
                if e.name != config_module_name:
                    raise
                Logger.debug(f"Module {module_py_name}'s config definition not found, skipped.")

        except Exception:
            # module() 与各组件装饰器都在导入期登记。若文件在登记一部分内容后
            # 才抛异常，必须撤销该包本轮产生的注册，否则报错模块仍可能接收命令。
            ModulesManager._restore_module_registrations(module_py_name, old_modules, old_origins)
            errmsg = f"Failed to load {module_py_name}: \n{traceback.format_exc()}"
            Logger.error(errmsg)
            err_prompt.append(errmsg)

    ModulesManager.refresh_modules_aliases()
    module_names = list(ModulesManager.modules.keys())
    module_aliases = {
        module_name: ModulesManager.get_module_and_alias_first_words(module_name) for module_name in module_names
    }
    await ModuleStatus.init_modules(module_names, module_aliases)
    # 一次取回全部状态：逐模块查询会退化成 N 次往返，模块多或主库在远端时开销可观
    module_status = dict(await ModuleStatus.all().values_list("module_name", "load"))
    for module_name, module in ModulesManager.modules.items():
        if (module_name in module_status and not module_status[module_name]) or not module.load:
            module._db_load = False
        if module._db_load:
            ModuleRuntimeManager.activate(module_name)
        else:
            await ModuleRuntimeManager.suspend(module_name)

    Logger.success("All modules loaded.")

    loader_cache = PrivateAssets.path / ".cache_loader"
    with open(loader_cache, "w", encoding="utf-8") as open_loader_cache:
        if err_prompt:
            err_prompt = re.sub(r"  File \"<frozen importlib.*?>\", .*?\n", "", "\n".join(err_prompt))
            open_loader_cache.write(err_prompt)
        else:
            open_loader_cache.write("")

    ModulesManager.refresh()
    for module_name in ModulesManager.modules:
        py_module = ModulesManager.return_py_module(module_name)
        if py_module:
            ModulesManager._locale_fingerprints.setdefault(py_module, ModulesManager._locale_fingerprint(py_module))


class ModulesManager:
    modules: dict[str, Module] = {}
    modules_aliases: dict[str, str] = {}
    modules_hooks: dict[str, Callable] = {}
    modules_hook_modules: dict[str, str] = {}
    modules_events: dict[str, list[tuple[str, EventMeta]]] = {}
    modules_origin: dict[str, str] = {}
    _deferred_bindings = []
    _reload_lock = asyncio.Lock()
    _reload_package: str | None = None
    _locale_fingerprints: dict[str, tuple[tuple[str, str], ...]] = {}
    _dependency_graph: dict[str, set[str]] = {}

    @classmethod
    def _locale_fingerprint(cls, py_module: str) -> tuple[tuple[str, str], ...]:
        module = sys.modules.get(py_module)
        module_file = getattr(module, "__file__", None)
        if not module_file:
            return ()
        locale_path = Path(module_file).resolve().parent / "locales"
        if not locale_path.is_dir():
            return ()
        fingerprints = []
        for locale_file in sorted(locale_path.rglob("*.json")):
            digest = hashlib.sha256(locale_file.read_bytes()).hexdigest()
            fingerprints.append((str(locale_file.relative_to(locale_path)), digest))
        return tuple(fingerprints)

    @classmethod
    def _sync_config_fields(cls, py_module: str) -> list[str]:
        """Create missing module config fields through the authorized config writer."""
        config_module_name = f"{py_module}.config"
        config_module = sys.modules.get(config_module_name)
        if config_module is None:
            return []

        errors = []
        for value in vars(config_module).values():
            fields = getattr(value, "__config_fields__", None)
            if not isinstance(fields, dict):
                continue
            for field_name, field in fields.items():
                try:
                    if CFGManager.has(field_name, field["secret"], field["table_name"]):
                        continue
                    default = field.get("default")
                    if default is None:
                        errors.append(f"{config_module_name}.{field_name}: missing value requires pre-init generation")
                        continue
                    CFGManager.edit_write(
                        field_name,
                        default,
                        field.get("cfg_type"),
                        field["secret"],
                        field["table_name"],
                    )
                except Exception as e:
                    errors.append(f"{config_module_name}.{field_name}: {e}")
        return errors

    @classmethod
    def _model_schema_fingerprint(cls, py_module: str) -> tuple[tuple, ...]:
        """Return a stable structural fingerprint for a module's ORM models."""
        models_module = f"{py_module}.database.models"
        try:
            spec = importlib.util.find_spec(models_module)
        except (ModuleNotFoundError, ValueError):
            return ()
        if spec is None:
            return ()
        try:
            module = importlib.import_module(models_module)
        except ModuleNotFoundError as e:
            if e.name in {f"{py_module}.database", models_module}:
                return ()
            raise

        tables = []
        for _, model in inspect.getmembers(module, inspect.isclass):
            if model is DBModel or not issubclass(model, DBModel):
                continue
            meta = getattr(model, "Meta", None)
            table_name = getattr(meta, "table", None)
            if not table_name:
                continue
            fields = []
            for field_name, field_obj in model._meta.fields_map.items():
                fields.append(
                    (
                        field_name,
                        type(field_obj).__name__,
                        str(getattr(field_obj, "max_length", "")),
                        bool(getattr(field_obj, "null", False)),
                        bool(getattr(field_obj, "pk", False)),
                    )
                )
            tables.append((table_name, tuple(sorted(fields))))
        return tuple(sorted(tables))

    @classmethod
    def add_module(cls, module: Module, py_module_name: str):
        if module.module_name not in cls.modules:
            cls.modules[module.module_name] = module
            cls.modules_origin[module.module_name] = py_module_name
            if cls._reload_package:
                deferred = []
                for deferred_module, meta in cls._deferred_bindings:
                    if deferred_module == module.module_name:
                        cls.bind_to_module(deferred_module, meta)
                    else:
                        deferred.append((deferred_module, meta))
                cls._deferred_bindings = deferred
        else:
            raise ValueError(f'Duplicate bind prefix "{module.module_name}"')

    @classmethod
    def remove_modules(cls, modules):
        for module in modules:
            if module in cls.modules:
                cls.modules.pop(module)
                cls.modules_origin.pop(module)
            else:
                raise ValueError(f'Module "{module}" is not exist.')

    @classmethod
    def refresh_modules_aliases(cls):
        cls.modules_aliases.clear()
        for m in cls.modules:
            module = cls.modules[m]
            if module.alias:
                cls.modules_aliases.update(module.alias)

    @classmethod
    def get_module_and_alias_first_words(cls, module_or_alias: str) -> list[str]:
        """返回模块名及其所有别名的首词。"""
        input_words = module_or_alias.split(maxsplit=1)
        if not input_words:
            return []

        first_word = input_words[0]
        module_name = first_word if first_word in cls.modules else None
        if not module_name:
            for alias, target in cls.modules_aliases.items():
                if alias.split(maxsplit=1)[0] == first_word:
                    module_name = target.split(maxsplit=1)[0]
                    break

        if not module_name or module_name not in cls.modules:
            return []

        result = [module_name]
        for alias, target in cls.modules_aliases.items():
            if target.split(maxsplit=1)[0] != module_name:
                continue
            alias_first_word = alias.split(maxsplit=1)[0]
            if alias_first_word not in result:
                result.append(alias_first_word)
        return result

    @classmethod
    def refresh_modules_hooks(cls):
        cls.modules_hooks.clear()
        cls.modules_hook_modules.clear()
        for m in cls.modules:
            module = cls.modules[m]
            if module.hooks_list:
                for hook in module.hooks_list.set:
                    hook_name = module.module_name + (("." + hook.name) if hook.name else "")
                    cls.modules_hooks.update({hook_name: hook.function})
                    cls.modules_hook_modules[hook_name] = module.module_name

    @classmethod
    def refresh_modules_events(cls):
        cls.modules_events.clear()
        for module_name, module in cls.modules.items():
            for event in module.events_list.set:
                cls.modules_events.setdefault(event.name, []).append((module_name, event))

    @classmethod
    def refresh(cls):
        cls.refresh_modules_aliases()
        cls.refresh_modules_hooks()
        cls.refresh_modules_events()
        cls._return_cache.clear()

    @classmethod
    async def dispatch_event(cls, event_info: EventInfo):
        if not isinstance(event_info, EventInfo):
            raise TypeError("event_info must be an EventInfo")

        target_from = event_info.target_from
        target_union_info = event_info.target_union_info
        available_modules = cls.return_modules_list(target_from, event_info.client_name) if target_from else cls.modules
        handler_functions = []
        for module_name, event_meta in cls.modules_events.get(event_info.event_name, []):
            module = cls.modules.get(module_name)
            if not module or not module._db_load or module_name not in available_modules:
                continue
            if event_meta not in module.events_list.get(target_from):
                continue
            if target_union_info and not module.base and module_name not in (target_union_info.modules or []):
                continue
            handler_functions.append((module_name, event_meta.function))
        if handler_functions:

            async def invoke(module_name: str, function: Callable, event_info: EventInfo):
                async with ModuleRuntimeManager.use(module_name):
                    return await function(event_info)

            return await asyncio.gather(
                *[invoke(module_name, function, event_info) for module_name, function in handler_functions]
            )
        return []

    @classmethod
    def search_related_module(cls, module, include_self=True):
        if module in cls.modules_origin:
            modules = []
            py_module = cls.return_py_module(module)
            for m in cls.modules_origin:
                if cls._origin_belongs_to(cls.modules_origin[m], py_module):
                    modules.append(m)
            if not include_self:
                modules.remove(module)
            return modules
        raise ValueError(f'Could not find "{module}" in modules_origin dict')

    @staticmethod
    def _origin_belongs_to(origin: str, py_module: str) -> bool:
        return origin == py_module or origin.startswith(f"{py_module}.")

    @classmethod
    def _module_names_for_py_module(cls, py_module: str) -> list[str]:
        return [
            module_name
            for module_name, origin in cls.modules_origin.items()
            if cls._origin_belongs_to(origin, py_module)
        ]

    @classmethod
    def _restore_module_registrations(
        cls,
        py_module: str,
        modules: dict[str, Module],
        origins: dict[str, str],
    ):
        for module_name in cls._module_names_for_py_module(py_module):
            cls.modules.pop(module_name, None)
            cls.modules_origin.pop(module_name, None)
        cls.modules.update(modules)
        cls.modules_origin.update(origins)
        cls.refresh()

    @classmethod
    def return_py_module(cls, module):
        if module in cls.modules_origin:
            return re.match(r"^modules(\.[a-zA-Z0-9_]*)?", cls.modules_origin[module]).group()
        return None

    @staticmethod
    def _normalize_package_name(module_name: str) -> str | None:
        parts = module_name.split(".")
        if len(parts) >= 2 and parts[0] == "modules":
            return ".".join(parts[:2])
        return None

    @classmethod
    def _scan_package_dependencies(cls, package_name: str) -> set[str]:
        module = sys.modules.get(package_name)
        if module is None:
            return set()
        paths = [Path(path) for path in getattr(module, "__path__", ())]
        module_file = getattr(module, "__file__", None)
        if not paths and module_file:
            paths = [Path(module_file)]
        source_files = []
        for path in paths:
            if path.is_dir():
                source_files.extend(path.rglob("*.py"))
            elif path.suffix == ".py":
                source_files.append(path)
        dependencies = set()
        for source_file in source_files:
            if any(part == "locales" for part in source_file.parts):
                continue
            try:
                tree = ast.parse(source_file.read_text(encoding="utf-8"))
            except (OSError, SyntaxError, UnicodeDecodeError):
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported = (alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported = (node.module,)
                else:
                    continue
                for imported_name in imported:
                    dependency = cls._normalize_package_name(imported_name)
                    if dependency and dependency != package_name:
                        dependencies.add(dependency)
        return dependencies

    @classmethod
    def _rebuild_dependency_graph(cls):
        packages = {py_module for m in cls.modules if (py_module := cls.return_py_module(m))}
        cls._dependency_graph = {
            package_name: cls._scan_package_dependencies(package_name) & packages for package_name in packages
        }

    @classmethod
    def _reload_closure(cls, py_module: str) -> list[str]:
        """Return the dependency-first package reload closure for ``py_module``."""
        cls._rebuild_dependency_graph()
        dependents: dict[str, set[str]] = {package_name: set() for package_name in cls._dependency_graph}
        for package_name, dependencies in cls._dependency_graph.items():
            for dependency in dependencies:
                dependents.setdefault(dependency, set()).add(package_name)

        included = set()
        stack = [py_module]
        while stack:
            package_name = stack.pop()
            if package_name in included:
                continue
            included.add(package_name)
            stack.extend(dependents.get(package_name, ()))

        ordered = []
        visiting = set()
        visited = set()

        def visit(package_name: str):
            if package_name in visited:
                return
            if package_name in visiting:
                return
            visiting.add(package_name)
            for dependency in sorted(cls._dependency_graph.get(package_name, ()) & included):
                visit(dependency)
            visiting.discard(package_name)
            visited.add(package_name)
            ordered.append(package_name)

        for package_name in sorted(included):
            visit(package_name)
        return ordered

    @classmethod
    def _module_names_for_py_modules(cls, py_modules: set[str]) -> list[str]:
        return [
            module_name
            for module_name, origin in cls.modules_origin.items()
            if cls.return_py_module(module_name) in py_modules
        ]

    @classmethod
    def bind_to_module(
        cls,
        module_name: str,
        meta: CommandMeta | RegexMeta | ScheduleMeta | HookMeta | EventMeta,
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
            elif isinstance(meta, EventMeta):
                cls.modules[module_name].events_list.add(meta)
        elif cls._reload_package:
            # 子模块会按 sys.modules 的顺序重载，扩展另一个兄弟模块的装饰器可能
            # 先于目标模块本身执行。等目标 module() 重新注册后再绑定，避免命令、
            # Hook 或 Event 在一次“成功”的热重载后静默消失。
            cls._deferred_bindings.append((module_name, meta))

    _return_cache = {}

    @classmethod
    def return_modules_list(
        cls, target_from: str | None = None, client_name: str | None = None, use_cache: bool = True
    ) -> dict[str, Module]:
        # 过滤结果同时取决于 target_from 与 client_name，缓存键必须两者都带上：
        # 只按 target_from 建键时，同一场景前缀配上不同的客户端名会取到上一次的结果。
        cache_key = (target_from, client_name)
        if target_from and use_cache and cache_key in cls._return_cache:
            return cls._return_cache[cache_key]
        modules = {module_name: cls.modules[module_name] for module_name in sorted(cls.modules)}

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
            cls._return_cache[cache_key] = returns
            return returns
        return modules

    @classmethod
    async def load_module(cls, module_name: str):
        """
        全域加载该机器人模块。
        """
        if module_name in cls.modules:
            module = cls.modules[module_name]
            old_load = module._db_load
            async with SchedulerLifecycle.maintenance_window({module_name}):
                try:
                    await ModuleStatus.set_module_loaded(module_name, True)
                    module._db_load = True
                    SchedulerLifecycle.reconcile_modules({module_name}, cls.modules)
                    ModuleRuntimeManager.activate(module_name)
                except BaseException:
                    # Scheduler 注册异常或取消不能留下“数据库显示启用、实际无 Job”状态。
                    try:
                        await asyncio.shield(ModuleStatus.set_module_loaded(module_name, old_load))
                        module._db_load = old_load
                        SchedulerLifecycle.reconcile_modules({module_name}, cls.modules)
                        if old_load:
                            ModuleRuntimeManager.activate(module_name)
                        else:
                            await ModuleRuntimeManager.suspend(module_name)
                    except Exception:
                        Logger.exception(f"Failed to restore module load state for {module_name}:")
                    raise
            return True
        return False

    @classmethod
    async def unload_module(cls, module_name: str):
        """
        全域卸载该机器人模块。
        """
        if module_name in cls.modules:
            module = cls.modules[module_name]
            old_load = module._db_load
            async with SchedulerLifecycle.maintenance_window({module_name}):
                try:
                    await ModuleStatus.set_module_loaded(module_name, False)
                    module._db_load = False
                    SchedulerLifecycle.reconcile_modules({module_name}, cls.modules)
                    await ModuleRuntimeManager.suspend(module_name)
                except BaseException:
                    try:
                        await asyncio.shield(ModuleStatus.set_module_loaded(module_name, old_load))
                        module._db_load = old_load
                        SchedulerLifecycle.reconcile_modules({module_name}, cls.modules)
                        if old_load:
                            ModuleRuntimeManager.activate(module_name)
                        else:
                            await ModuleRuntimeManager.suspend(module_name)
                    except Exception:
                        Logger.exception(f"Failed to restore module unload state for {module_name}:")
                    raise
            return True
        return False

    @classmethod
    async def reload_module(cls, module_name: str):
        """
        重载该机器人模块（以及该模块所在文件的其它模块）
        """
        # 此处不能等待另一个重载释放锁：先进入数据库维护的重载会等待其它
        # JobQueue action 收尾，而第二个 action 若阻塞在本锁上，双方会形成死锁。
        # 忙碌时直接失败也能保证第二次请求尚未改动模块注册表。
        if cls._reload_lock.locked():
            Logger.warning(f"Another module reload is already in progress, skipped {module_name}.")
            return False, 0

        async with cls._reload_lock:
            # 先排空 Queue handler，再进入 Scheduler 维护。反序会让正在执行
            # load/unload 的 handler 卡在 Scheduler 锁上，而 reload 又在等该
            # handler 收尾，形成永久互锁。Scheduler 窗口仍须覆盖 importlib.reload()：
            # 旧函数的 __globals__ 指向会被原地更新的模块字典。
            from core.queue.server import JobQueueServer

            async with JobQueueServer.maintenance_window():
                async with SchedulerLifecycle.maintenance_window():
                    return await cls._reload_module(module_name)

    @classmethod
    async def _reload_module(cls, module_name: str):
        py_module = cls.return_py_module(module_name)
        reload_packages = cls._reload_closure(py_module)
        reload_package_set = set(reload_packages)
        related_modules = cls._module_names_for_py_modules(reload_package_set)
        locale_fingerprints = {package_name: cls._locale_fingerprint(package_name) for package_name in reload_packages}
        changed_locale_packages = {
            package_name
            for package_name, fingerprint in locale_fingerprints.items()
            if fingerprint and cls._locale_fingerprints.get(package_name) != fingerprint
        }
        old_schema_fingerprints = {
            package_name: cls._model_schema_fingerprint(package_name) for package_name in reload_packages
        }
        runtime_snapshot = ModuleRuntimeManager.prepare_reload(set(related_modules))
        runtime_names = set(related_modules)
        old_modules = {name: cls.modules[name] for name in related_modules}
        old_origins = {name: cls.modules_origin[name] for name in related_modules}
        old_deferred_bindings = cls._deferred_bindings
        old_reload_package = cls._reload_package
        status_names_to_replace = set(related_modules)
        statuses_replaced = False
        registrations_replaced = False
        count = -999
        old_statuses = {}
        scheduler_names_to_replace = set(related_modules)
        old_schedules = SchedulerLifecycle.snapshot_modules(scheduler_names_to_replace)
        schedules_replaced = False

        def restore_registrations():
            for package_name in reversed(reload_packages):
                cls._restore_module_registrations(package_name, old_modules, old_origins)

        async def restore_statuses():
            await ModuleStatus.filter(module_name__in=status_names_to_replace).delete()
            if old_statuses:
                await ModuleStatus.bulk_create(
                    [ModuleStatus(module_name=name, load=load) for name, load in old_statuses.items()]
                )

        try:
            old_statuses = dict(
                await ModuleStatus.filter(module_name__in=related_modules).values_list("module_name", "load")
            )

            cls._reload_package = py_module
            cls._deferred_bindings = []
            cls.remove_modules(related_modules)
            registrations_replaced = True
            count = 0
            for package_name in reload_packages:
                package_count = cls.reload_py_module(package_name)
                if package_count < 0:
                    count = -999
                    break
                count += package_count
            if count <= 0:
                runtime_names.update(cls._module_names_for_py_modules(reload_package_set))
                restore_registrations()
                ModuleRuntimeManager.abort_reload(runtime_snapshot, runtime_names)
                return False, count

            reloaded_modules = cls._module_names_for_py_modules(reload_package_set)
            runtime_names.update(reloaded_modules)
            if not reloaded_modules:
                Logger.error(f"Reloaded Python packages {reload_packages}, but they did not register any modules.")
                restore_registrations()
                ModuleRuntimeManager.abort_reload(runtime_snapshot, runtime_names)
                return False, count

            config_errors = []
            for package_name in reload_packages:
                config_errors.extend(cls._sync_config_fields(package_name))
            if config_errors:
                Logger.error(f"Failed to synchronize module configuration for {reload_packages}: {config_errors}")
                restore_registrations()
                ModuleRuntimeManager.abort_reload(runtime_snapshot, runtime_names)
                return False, count

            changed_schema_packages = [
                package_name
                for package_name in reload_packages
                if cls._model_schema_fingerprint(package_name) != old_schema_fingerprints.get(package_name, ())
            ]
            if changed_schema_packages:
                Logger.error(
                    f"Database model schema changed during reload for {changed_schema_packages}; "
                    "restart and run database migration instead."
                )
                restore_registrations()
                ModuleRuntimeManager.abort_reload(runtime_snapshot, runtime_names)
                return False, count

            if cls._deferred_bindings:
                missing_modules = sorted({name for name, _ in cls._deferred_bindings})
                Logger.warning(
                    f"Dropped deferred component bindings for modules not registered by "
                    f"{reload_packages}: {missing_modules}"
                )

            cls.refresh()
            new_statuses = {}
            for name in reloaded_modules:
                module = cls.modules[name]
                load = old_statuses.get(name)
                if load is None:
                    alias_first_words = {alias.split(maxsplit=1)[0] for alias in (module.alias or ())}
                    old_name = next((alias for alias in alias_first_words if alias in old_statuses), None)
                    load = old_statuses[old_name] if old_name else True
                new_statuses[name] = load
                module._db_load = bool(load and module.load)

            status_names_to_replace.update(reloaded_modules)
            scheduler_names_to_replace.update(reloaded_modules)
            # 在首个会修改持久化状态的 await 之前置位。协程可能恰好在 delete()
            # 提交后收到取消；若等 await 返回才置位，取消路径会误判为无需回滚。
            statuses_replaced = True
            await ModuleStatus.filter(module_name__in=status_names_to_replace).delete()
            if new_statuses:
                await ModuleStatus.bulk_create(
                    [ModuleStatus(module_name=name, load=load) for name, load in new_statuses.items()]
                )

            # Scheduler 当前仍处于维护窗口，先把新 Job 准备好但不允许执行；数据库
            # 重载失败时可连同 ModuleStatus 与注册表一起恢复旧 Job。
            SchedulerLifecycle.reconcile_modules(scheduler_names_to_replace, cls.modules)
            schedules_replaced = True

            if not await reload_db():
                Logger.error(f"Reloaded Python module {py_module}, but failed to reinitialize its database models.")
                await restore_statuses()
                statuses_replaced = False
                restore_registrations()
                SchedulerLifecycle.restore_modules(old_schedules, scheduler_names_to_replace)
                schedules_replaced = False
                ModuleRuntimeManager.abort_reload(runtime_snapshot, runtime_names)
                return False, count

            active_modules = {
                name
                for name in runtime_names
                if name in cls.modules and cls.modules[name]._db_load and cls.modules[name].load
            }
            await ModuleRuntimeManager.commit_reload(runtime_snapshot, runtime_names, active_modules)
            if changed_locale_packages:
                try:
                    locale_errors = build_locale_snapshot(list(lang_list.keys()), all_locales_path, "akari-bot")
                    if locale_errors:
                        Logger.warning(
                            f"Failed to rebuild locale snapshot after reloading {reload_packages}: {locale_errors}"
                        )
                    else:
                        for package_name in changed_locale_packages:
                            cls._locale_fingerprints[package_name] = locale_fingerprints[package_name]
                except Exception:
                    Logger.exception(f"Failed to rebuild locale snapshot after reloading {py_module}:")
            return True, count
        except asyncio.CancelledError:
            # Queue action 超时或 Server 关闭都会取消热重载。取消不能被转换成普通
            # 失败，但在继续传播前必须恢复已删改的持久状态与内存注册表。
            if statuses_replaced:
                try:
                    await asyncio.shield(restore_statuses())
                except Exception:
                    Logger.exception(f"Failed to restore ModuleStatus rows for cancelled reload of {py_module}:")
            runtime_names.update(cls._module_names_for_py_modules(reload_package_set))
            if registrations_replaced:
                restore_registrations()
            if schedules_replaced:
                SchedulerLifecycle.restore_modules(old_schedules, scheduler_names_to_replace)
            ModuleRuntimeManager.abort_reload(runtime_snapshot, runtime_names)
            raise
        except Exception:
            Logger.exception(f"Failed to reload module package {py_module}:")
            runtime_names.update(cls._module_names_for_py_modules(reload_package_set))
            if statuses_replaced:
                try:
                    await restore_statuses()
                except Exception:
                    Logger.exception(f"Failed to restore ModuleStatus rows for {py_module}:")
            if registrations_replaced:
                restore_registrations()
            if schedules_replaced:
                SchedulerLifecycle.restore_modules(old_schedules, scheduler_names_to_replace)
            ModuleRuntimeManager.abort_reload(runtime_snapshot, runtime_names)
            return False, count
        finally:
            cls._deferred_bindings = old_deferred_bindings
            cls._reload_package = old_reload_package

    @classmethod
    def reload_py_module(cls, module_name: str):
        """
        重载该Python模块
        """
        module_names = [name for name in sys.modules if name == module_name or name.startswith(f"{module_name}.")]
        if module_name not in module_names:
            Logger.error(f"Cannot reload unknown Python module {module_name}.")
            return -999
        snapshot = {name: sys.modules[name] for name in module_names}
        try:
            Logger.info(f"Reloading {module_name} with a fresh module namespace ...")
            for name in module_names:
                sys.modules.pop(name, None)
            for name in module_names:
                importlib.import_module(name)
            loaded_module_names = [
                name for name in sys.modules if name == module_name or name.startswith(f"{module_name}.")
            ]
            Logger.success(f"Successfully reloaded {module_name}.")
            return len(loaded_module_names)
        except Exception:
            Logger.exception(f"Failed to reload {module_name}:")
            for name in list(sys.modules):
                if name == module_name or name.startswith(f"{module_name}."):
                    sys.modules.pop(name, None)
            sys.modules.update(snapshot)
            return -999
