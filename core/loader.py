import importlib
import asyncio
import pkgutil
import re
import sys
import traceback
from typing import Callable

from core.builtins.session.info import EventInfo
from core.constants import PrivateAssets
from core.database import reload_db
from core.database.models import ModuleStatus
from core.logger import Logger
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

    Logger.success("All modules loaded.")

    loader_cache = PrivateAssets.path / ".cache_loader"
    with open(loader_cache, "w", encoding="utf-8") as open_loader_cache:
        if err_prompt:
            err_prompt = re.sub(r"  File \"<frozen importlib.*?>\", .*?\n", "", "\n".join(err_prompt))
            open_loader_cache.write(err_prompt)
        else:
            open_loader_cache.write("")

    ModulesManager.refresh()


class ModulesManager:
    modules: dict[str, Module] = {}
    modules_aliases: dict[str, str] = {}
    modules_hooks: dict[str, Callable] = {}
    modules_events: dict[str, list[tuple[str, EventMeta]]] = {}
    modules_origin: dict[str, str] = {}
    _deferred_bindings = []
    _reload_lock = asyncio.Lock()
    _reload_package: str | None = None

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
        for m in cls.modules:
            module = cls.modules[m]
            if module.hooks_list:
                for hook in module.hooks_list.set:
                    hook_name = module.module_name + (("." + hook.name) if hook.name else "")
                    cls.modules_hooks.update({hook_name: hook.function})

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
            handler_functions.append(event_meta.function)
        if handler_functions:
            return await asyncio.gather(*[function(event_info) for function in handler_functions])
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
                except BaseException:
                    # Scheduler 注册异常或取消不能留下“数据库显示启用、实际无 Job”状态。
                    try:
                        await asyncio.shield(ModuleStatus.set_module_loaded(module_name, old_load))
                        module._db_load = old_load
                        SchedulerLifecycle.reconcile_modules({module_name}, cls.modules)
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
                except BaseException:
                    try:
                        await asyncio.shield(ModuleStatus.set_module_loaded(module_name, old_load))
                        module._db_load = old_load
                        SchedulerLifecycle.reconcile_modules({module_name}, cls.modules)
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
        # 不能在这里等待另一个重载释放锁：先进入数据库维护的重载会等待其它
        # JobQueue action 收尾，而第二个 action 若阻塞在本锁上，双方会形成死锁。
        # 忙碌时直接失败也能保证第二次请求尚未改动模块注册表。
        if cls._reload_lock.locked():
            Logger.warning(f"Another module reload is already in progress, skipped {module_name}.")
            return False, 0

        async with cls._reload_lock:
            # 必须在 importlib.reload() 之前排空 schedule；旧函数的 __globals__ 指向
            # 会被原地更新的模块字典，只保护 reload_db() 已经太晚。
            async with SchedulerLifecycle.maintenance_window():
                return await cls._reload_module(module_name)

    @classmethod
    async def _reload_module(cls, module_name: str):
        py_module = cls.return_py_module(module_name)
        related_modules = cls.search_related_module(module_name)
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
            count = cls.reload_py_module(py_module)
            if count <= 0:
                cls._restore_module_registrations(py_module, old_modules, old_origins)
                return False, count

            reloaded_modules = cls._module_names_for_py_module(py_module)
            if not reloaded_modules:
                Logger.error(f"Reloaded Python package {py_module}, but it did not register any modules.")
                cls._restore_module_registrations(py_module, old_modules, old_origins)
                return False, count

            if cls._deferred_bindings:
                missing_modules = sorted({name for name, _ in cls._deferred_bindings})
                Logger.warning(
                    f"Dropped deferred component bindings for modules not registered by {py_module}: {missing_modules}"
                )

            cls.refresh()
            new_statuses = {}
            for name in reloaded_modules:
                module = cls.modules[name]
                load = old_statuses.get(name)
                if load is None:
                    alias_first_words = {alias.split(maxsplit=1)[0] for alias in module.alias}
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
                cls._restore_module_registrations(py_module, old_modules, old_origins)
                SchedulerLifecycle.restore_modules(old_schedules, scheduler_names_to_replace)
                schedules_replaced = False
                return False, count

            return True, count
        except asyncio.CancelledError:
            # Queue action 超时或 Server 关闭都会取消热重载。取消不能被转换成普通
            # 失败，但在继续传播前必须恢复已删改的持久状态与内存注册表。
            if statuses_replaced:
                try:
                    await asyncio.shield(restore_statuses())
                except Exception:
                    Logger.exception(f"Failed to restore ModuleStatus rows for cancelled reload of {py_module}:")
            if registrations_replaced:
                cls._restore_module_registrations(py_module, old_modules, old_origins)
            if schedules_replaced:
                SchedulerLifecycle.restore_modules(old_schedules, scheduler_names_to_replace)
            raise
        except Exception:
            Logger.exception(f"Failed to reload module package {py_module}:")
            if statuses_replaced:
                try:
                    await restore_statuses()
                except Exception:
                    Logger.exception(f"Failed to restore ModuleStatus rows for {py_module}:")
            if registrations_replaced:
                cls._restore_module_registrations(py_module, old_modules, old_origins)
            if schedules_replaced:
                SchedulerLifecycle.restore_modules(old_schedules, scheduler_names_to_replace)
            return False, count
        finally:
            cls._deferred_bindings = old_deferred_bindings
            cls._reload_package = old_reload_package

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
                suffix = mod.removeprefix(f"{module_name}.")
                if suffix != mod and "." not in suffix:
                    child_count = cls.reload_py_module(mod)
                    if child_count < 0:
                        return -999
                    cnt += child_count
            importlib.reload(module)
            Logger.success(f"Successfully reloaded {module_name}.")
            return cnt + 1
        except Exception:
            Logger.exception(f"Failed to reload {module_name}:")
            return -999
