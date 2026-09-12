"""core.loader 模块加载器单元测试。"""

import asyncio
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from types import ModuleType
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, call, patch

from apscheduler.triggers.interval import IntervalTrigger

import core.loader as loader_module
from core.config import CFGManager
from core.constants import PrivateAssets
from core.database.models import ModuleStatus
from core.loader import ModulesManager
from core.module_runtime import ModuleRuntimeManager
from core.queue.server import JobQueueServer
from core.scheduler import SchedulerLifecycle
from core.tester import func_case, Tester
from core.types import Module
from core.types.module.component_meta import CommandMeta, EventMeta, HookMeta, RegexMeta, ScheduleMeta


RENAMED_MODULES = {
    "arcaea-rss": "arcaea_rss",
    "chemical-code": "chemical_code",
    "exchange-rate": "exchange_rate",
    "feedback-news": "feedback_news",
    "maimai-regex": "maimai_regex",
    "mcbv-rss": "mcbv_rss",
    "mcv-rss": "mcv_rss",
    "minecraft-news": "minecraft_news",
    "mod-dl": "mod_dl",
    "mojang-status": "mojang_status",
    "nintendo-err": "nintendo_err",
    "post-whitelist": "post_whitelist",
    "teahouse-weekly-rss": "teahouse_weekly_rss",
    "twenty-four": "twenty_four",
    "weekly-rss": "weekly_rss",
    "wiki-audit": "wiki_audit",
    "wiki-bot": "wiki_bot",
    "wiki-inline": "wiki_inline",
}


def _test_add_module():
    """ModulesManager.add_module: 添加模块"""
    try:
        test_module = Module.assign(
            module_name="__test_loader_mod_1", alias=None, recommend_modules=None, developers=None
        )
        ModulesManager.add_module(test_module, "test.py")
        result = "__test_loader_mod_1" in ModulesManager.modules
        ModulesManager.modules.pop("__test_loader_mod_1", None)
        ModulesManager.modules_origin.pop("__test_loader_mod_1", None)
        return result
    except Exception:
        return False


def _test_add_module_duplicate():
    """ModulesManager.add_module: 重复添加应抛出 ValueError"""
    try:
        test_module = Module.assign(
            module_name="__test_loader_mod_2", alias=None, recommend_modules=None, developers=None
        )
        ModulesManager.add_module(test_module, "test.py")
        try:
            duplicate = Module.assign(
                module_name="__test_loader_mod_2", alias=None, recommend_modules=None, developers=None
            )
            ModulesManager.add_module(duplicate, "test.py")
            ModulesManager.modules.pop("__test_loader_mod_2", None)
            ModulesManager.modules_origin.pop("__test_loader_mod_2", None)
            return False
        except ValueError:
            ModulesManager.modules.pop("__test_loader_mod_2", None)
            ModulesManager.modules_origin.pop("__test_loader_mod_2", None)
            return True
    except Exception:
        return False


def _test_remove_modules():
    """ModulesManager.remove_modules: 移除模块"""
    try:
        test_module = Module.assign(
            module_name="__test_loader_mod_3", alias=None, recommend_modules=None, developers=None
        )
        ModulesManager.add_module(test_module, "test.py")
        ModulesManager.remove_modules(["__test_loader_mod_3"])
        return "__test_loader_mod_3" not in ModulesManager.modules
    except Exception:
        return False


def _test_remove_nonexistent_module():
    """ModulesManager.remove_modules: 移除不存在的模块应抛出 ValueError"""
    try:
        ModulesManager.remove_modules(["__nonexistent_module_xyz_12345__"])
        return False
    except ValueError:
        return True
    except Exception:
        return False


def _test_bind_to_module_command():
    """ModulesManager.bind_to_module: 绑定 CommandMeta"""
    try:
        test_module = Module.assign(
            module_name="__test_loader_bind_1", alias=None, recommend_modules=None, developers=None
        )
        ModulesManager.add_module(test_module, "test.py")

        async def dummy_func(msg):
            pass

        meta = CommandMeta(function=dummy_func, command_template=[])
        ModulesManager.bind_to_module("__test_loader_bind_1", meta)
        result = len(ModulesManager.modules["__test_loader_bind_1"].command_list.set) == 1
        ModulesManager.modules.pop("__test_loader_bind_1", None)
        ModulesManager.modules_origin.pop("__test_loader_bind_1", None)
        return result
    except Exception:
        return False


def _test_bind_to_module_regex():
    """ModulesManager.bind_to_module: 绑定 RegexMeta"""
    try:
        test_module = Module.assign(
            module_name="__test_loader_bind_2", alias=None, recommend_modules=None, developers=None
        )
        ModulesManager.add_module(test_module, "test.py")

        async def dummy_func(msg):
            pass

        meta = RegexMeta(function=dummy_func, pattern=r"test")
        ModulesManager.bind_to_module("__test_loader_bind_2", meta)
        result = len(ModulesManager.modules["__test_loader_bind_2"].regex_list.set) == 1
        ModulesManager.modules.pop("__test_loader_bind_2", None)
        ModulesManager.modules_origin.pop("__test_loader_bind_2", None)
        return result
    except Exception:
        return False


def _test_bind_to_nonexistent_module():
    """ModulesManager.bind_to_module: 绑定到不存在的模块应静默忽略"""
    try:
        meta = CommandMeta(function=lambda m: None, command_template=[])
        ModulesManager.bind_to_module("__nonexistent_xyz__", meta)
        return True
    except Exception:
        return False


def _test_return_modules_list():
    """ModulesManager.return_modules_list: 返回所有模块"""
    try:
        test_module = Module.assign(
            module_name="__test_loader_list_1", alias=None, recommend_modules=None, developers=None
        )
        test_module._db_load = True
        ModulesManager.add_module(test_module, "test.py")
        modules = ModulesManager.return_modules_list()
        result = "__test_loader_list_1" in modules
        ModulesManager.modules.pop("__test_loader_list_1", None)
        ModulesManager.modules_origin.pop("__test_loader_list_1", None)
        return result
    except Exception:
        return False


def _test_return_modules_list_filter_platform():
    """ModulesManager.return_modules_list: 按平台过滤"""
    try:
        test_module = Module.assign(
            module_name="__test_loader_filter_1",
            alias=None,
            recommend_modules=None,
            developers=None,
            available_for=["QQ"],
        )
        test_module._db_load = True
        ModulesManager.add_module(test_module, "test.py")
        ModulesManager.refresh()

        qq_modules = ModulesManager.return_modules_list(target_from="QQ", client_name="QQ")
        discord_modules = ModulesManager.return_modules_list(target_from="Discord", client_name="Discord")

        qq_has = "__test_loader_filter_1" in qq_modules
        discord_has = "__test_loader_filter_1" in discord_modules

        ModulesManager.modules.pop("__test_loader_filter_1", None)
        ModulesManager.modules_origin.pop("__test_loader_filter_1", None)
        ModulesManager.refresh()

        return qq_has and not discord_has
    except Exception:
        return False


def _test_refresh_aliases():
    """ModulesManager.refresh_modules_aliases: 刷新别名"""
    try:
        test_module = Module.assign(
            module_name="__test_loader_alias_1",
            alias={"ta": "__test_loader_alias_1"},
            recommend_modules=None,
            developers=None,
        )
        ModulesManager.add_module(test_module, "test.py")
        ModulesManager.refresh_modules_aliases()
        result = ModulesManager.modules_aliases.get("ta") == "__test_loader_alias_1"
        ModulesManager.modules.pop("__test_loader_alias_1", None)
        ModulesManager.modules_origin.pop("__test_loader_alias_1", None)
        return result
    except Exception:
        return False


def _test_get_module_and_alias_first_words():
    """ModulesManager.get_module_and_alias_first_words: 查找模块与别名首词"""
    module_name = "__test_loader_related"
    try:
        test_module = Module.assign(
            module_name=module_name,
            alias={
                "__test_loader_related_alias": module_name,
                "__test_loader_related_alias detail": f"{module_name} detail",
                "__test_loader_related_alt info": f"{module_name} info",
            },
            recommend_modules=None,
            developers=None,
        )
        ModulesManager.add_module(test_module, "test.py")
        ModulesManager.refresh_modules_aliases()
        expected = [module_name, "__test_loader_related_alias", "__test_loader_related_alt"]
        return (
            ModulesManager.get_module_and_alias_first_words(module_name) == expected
            and ModulesManager.get_module_and_alias_first_words("__test_loader_related_alias") == expected
            and ModulesManager.get_module_and_alias_first_words("__test_loader_related_alt") == expected
            and ModulesManager.get_module_and_alias_first_words("__test_loader_related_missing") == []
        )
    except Exception:
        return False
    finally:
        ModulesManager.modules.pop(module_name, None)
        ModulesManager.modules_origin.pop(module_name, None)
        ModulesManager.refresh_modules_aliases()


def _test_renamed_modules_keep_legacy_aliases():
    """带下划线的旧模块名应保留为新主名的命令别名。"""
    return all(
        new_name in ModulesManager.modules and ModulesManager.modules_aliases.get(old_name) == new_name
        for new_name, old_name in RENAMED_MODULES.items()
    )


async def _test_module_status_alias_migration():
    """ModuleStatus 应在主名迁移时保留旧模块的加载状态。"""
    new_name = "__test-loader-status-new"
    old_name = "__test_loader_status_old"
    current_modules = await ModuleStatus.get_all_modules()
    try:
        await ModuleStatus.filter(module_name__in=[new_name, old_name]).delete()
        await ModuleStatus.create(module_name=old_name, load=False)
        await ModuleStatus.init_modules(
            current_modules + [new_name],
            {new_name: [new_name, old_name]},
        )
        migrated = await ModuleStatus.get_or_none(module_name=new_name)
        return bool(migrated and not migrated.load and not await ModuleStatus.filter(module_name=old_name).exists())
    finally:
        await ModuleStatus.filter(module_name__in=[new_name, old_name]).delete()


def _snapshot_module_manager():
    return (
        dict(ModulesManager.modules),
        dict(ModulesManager.modules_origin),
        list(ModulesManager._deferred_bindings),
        ModulesManager._reload_package,
    )


def _restore_module_manager(snapshot):
    modules, origins, deferred_bindings, reload_package = snapshot
    ModulesManager.modules.clear()
    ModulesManager.modules.update(modules)
    ModulesManager.modules_origin.clear()
    ModulesManager.modules_origin.update(origins)
    ModulesManager._deferred_bindings = deferred_bindings
    ModulesManager._reload_package = reload_package
    ModulesManager.refresh()


@asynccontextmanager
async def _patch_database_reload(prepare):
    with patch.multiple(
        loader_module,
        prepare_db_reload=prepare,
        activate_db_reload=MagicMock(),
        close_prepared_db_reload=AsyncMock(),
        close_previous_db_context=AsyncMock(),
    ) as patched:
        yield patched


def _reload_test_module(name: str, alias: str, origin: str, hook_function, event_function, load: bool = True):
    module = Module.assign(
        module_name=name,
        alias=alias,
        recommend_modules=None,
        developers=None,
        load=load,
    )
    module.hooks_list.add(HookMeta(function=hook_function, name="reload"))
    module.events_list.add(EventMeta(function=event_function, name="reload-event"))
    ModulesManager.add_module(module, origin)
    return module


async def _test_reload_preserves_mixed_status_and_rebuilds_registries():
    """同包模块重载后须分别保留启用状态，并重建 origin、别名、Hook 与 Event。"""
    package = "modules.__test_loader_reload_success"
    first_name = "__test_loader_reload_success_first"
    second_name = "__test_loader_reload_success_second"
    test_names = [first_name, second_name]
    snapshot = _snapshot_module_manager()

    async def old_hook():
        return "old-hook"

    async def old_event(_):
        return "old-event"

    async def new_hook():
        return "new-hook"

    async def new_event(_):
        return "new-event"

    async def old_schedule():
        return "old-schedule"

    async def new_schedule():
        return "new-schedule"

    def reload_python(_):
        first = _reload_test_module(first_name, "__reload_first_new", f"{package}.first", new_hook, new_event)
        second = _reload_test_module(second_name, "__reload_second_new", f"{package}.second", new_hook, new_event)
        first.schedule_list.add(ScheduleMeta(function=new_schedule, trigger=IntervalTrigger(hours=1)))
        second.schedule_list.add(ScheduleMeta(function=new_schedule, trigger=IntervalTrigger(hours=1)))
        return 2

    try:
        first = _reload_test_module(first_name, "__reload_first_old", f"{package}.first", old_hook, old_event)
        second = _reload_test_module(second_name, "__reload_second_old", f"{package}.second", old_hook, old_event)
        first._db_load = False
        second._db_load = True
        first.schedule_list.add(ScheduleMeta(function=old_schedule, trigger=IntervalTrigger(hours=1)))
        second.schedule_list.add(ScheduleMeta(function=old_schedule, trigger=IntervalTrigger(hours=1)))
        SchedulerLifecycle.prepare()
        SchedulerLifecycle.reconcile_modules(test_names, ModulesManager.modules)
        ModulesManager.refresh()
        await ModuleStatus.filter(module_name__in=test_names).delete()
        await ModuleStatus.bulk_create(
            [ModuleStatus(module_name=first_name, load=False), ModuleStatus(module_name=second_name, load=True)]
        )

        with patch.object(ModulesManager, "reload_py_module", side_effect=reload_python):
            async with _patch_database_reload(AsyncMock(return_value=object())):
                success, count = await ModulesManager.reload_module(first_name)

        statuses = dict(await ModuleStatus.filter(module_name__in=test_names).values_list("module_name", "load"))
        event_entries = ModulesManager.modules_events.get("reload-event", [])
        return (
            success
            and count == 2
            and statuses == {first_name: False, second_name: True}
            and not ModulesManager.modules[first_name]._db_load
            and ModulesManager.modules[second_name]._db_load
            and ModulesManager.modules_origin[first_name] == f"{package}.first"
            and ModulesManager.modules_origin[second_name] == f"{package}.second"
            and ModulesManager.modules_aliases.get("__reload_first_new") == first_name
            and ModulesManager.modules_aliases.get("__reload_second_new") == second_name
            and ModulesManager.modules_hooks.get(f"{first_name}.reload") is new_hook
            and ModulesManager.modules_hooks.get(f"{second_name}.reload") is new_hook
            and {name for name, meta in event_entries if meta.function is new_event} == {first_name, second_name}
            and SchedulerLifecycle.module_job_id(first_name, 0) not in SchedulerLifecycle._job_specs
            and SchedulerLifecycle._job_specs[SchedulerLifecycle.module_job_id(second_name, 0)].function is new_schedule
        )
    finally:
        await ModuleStatus.filter(module_name__in=test_names).delete()
        SchedulerLifecycle._remove_modules(test_names)
        _restore_module_manager(snapshot)


async def _test_reload_accepts_new_aliasless_module():
    """无旧状态且 alias=None 的模块不能因读取空别名而让整次重载失败。"""
    package = "modules.__test_loader_reload_aliasless"
    module_name = "__test_loader_reload_aliasless"
    snapshot = _snapshot_module_manager()

    async def hook():
        return "hook"

    async def event(_):
        return "event"

    def reload_python(_):
        _reload_test_module(module_name, None, f"{package}.entry", hook, event)
        return 1

    try:
        old_module = _reload_test_module(
            module_name,
            "__test_loader_reload_aliasless_old",
            f"{package}.entry",
            hook,
            event,
        )
        old_module._db_load = False
        await ModuleStatus.filter(module_name=module_name).delete()

        with patch.object(ModulesManager, "reload_py_module", side_effect=reload_python):
            async with _patch_database_reload(AsyncMock(return_value=object())):
                success, count = await ModulesManager.reload_module(module_name)

        return (
            success
            and count == 1
            and ModulesManager.modules[module_name].alias is None
            and ModulesManager.modules[module_name]._db_load
        )
    finally:
        await ModuleStatus.filter(module_name=module_name).delete()
        _restore_module_manager(snapshot)


async def _test_reload_drains_queue_before_scheduler_maintenance():
    """reload 不能持 Scheduler 锁等待会再次申请该锁的 Queue handler。"""
    order = []

    @asynccontextmanager
    async def queue_window(*, exclusive=True):
        order.append("queue")
        order.append(f"queue_exclusive={exclusive}")
        yield

    @asynccontextmanager
    async def scheduler_window():
        order.append("scheduler")
        yield

    reload_impl = AsyncMock(return_value=(True, 1))
    with (
        patch.object(JobQueueServer, "maintenance_window", new=queue_window),
        patch.object(SchedulerLifecycle, "maintenance_window", new=scheduler_window),
        patch.object(ModulesManager, "_reload_module", new=reload_impl),
    ):
        result = await ModulesManager.reload_module("__test_loader_lock_order")

    return (
        result == (True, 1)
        and order == ["queue", "queue_exclusive=False", "scheduler"]
        and reload_impl.await_count == 1
    )


async def _test_reload_python_failure_restores_all_registries():
    """Python 重载中途失败时，部分新注册不能污染旧模块、别名、Hook 或 Event。"""
    package = "modules.__test_loader_reload_python_failure"
    module_name = "__test_loader_reload_python_failure"
    partial_name = "__test_loader_reload_partial"
    test_names = [module_name, partial_name]
    snapshot = _snapshot_module_manager()

    async def old_hook():
        return "old-hook"

    async def old_event(_):
        return "old-event"

    async def partial_hook():
        return "partial-hook"

    async def partial_event(_):
        return "partial-event"

    def reload_python(_):
        _reload_test_module(partial_name, "__partial_alias", f"{package}.partial", partial_hook, partial_event)
        return -999

    prepare_database = AsyncMock(return_value=object())
    try:
        old_module = _reload_test_module(
            module_name,
            "__old_reload_alias",
            f"{package}.entry",
            old_hook,
            old_event,
        )
        ModulesManager.refresh()
        await ModuleStatus.filter(module_name__in=test_names).delete()
        await ModuleStatus.create(module_name=module_name, load=False)

        with patch.object(ModulesManager, "reload_py_module", side_effect=reload_python):
            async with _patch_database_reload(prepare_database):
                success, count = await ModulesManager.reload_module(module_name)

        status = await ModuleStatus.get_or_none(module_name=module_name)
        events = ModulesManager.modules_events.get("reload-event", [])
        return (
            not success
            and count == -999
            and ModulesManager.modules.get(module_name) is old_module
            and partial_name not in ModulesManager.modules
            and ModulesManager.modules_origin.get(module_name) == f"{package}.entry"
            and ModulesManager.modules_aliases.get("__old_reload_alias") == module_name
            and "__partial_alias" not in ModulesManager.modules_aliases
            and ModulesManager.modules_hooks.get(f"{module_name}.reload") is old_hook
            and any(name == module_name and meta.function is old_event for name, meta in events)
            and status is not None
            and not status.load
            and prepare_database.await_count == 0
        )
    finally:
        await ModuleStatus.filter(module_name__in=test_names).delete()
        _restore_module_manager(snapshot)


async def _test_reload_reports_database_reinitialization_failure():
    """新数据库模型失败时须恢复旧模块注册和原 ModuleStatus，而不是只返回失败。"""
    package = "modules.__test_loader_reload_database_failure"
    module_name = "__test_loader_reload_database_failure"
    snapshot = _snapshot_module_manager()

    async def old_hook():
        return "old-hook"

    async def old_event(_):
        return "old-event"

    async def new_hook():
        return "new-hook"

    async def new_event(_):
        return "new-event"

    async def old_schedule():
        return "old-schedule"

    async def new_schedule():
        return "new-schedule"

    def reload_python(_):
        module = _reload_test_module(
            module_name,
            "__new_database_alias",
            f"{package}.entry",
            new_hook,
            new_event,
        )
        module.schedule_list.add(ScheduleMeta(function=new_schedule, trigger=IntervalTrigger(hours=1)))
        return 1

    try:
        old_module = _reload_test_module(
            module_name,
            "__old_database_alias",
            f"{package}.entry",
            old_hook,
            old_event,
        )
        old_module._db_load = True
        old_module.schedule_list.add(ScheduleMeta(function=old_schedule, trigger=IntervalTrigger(hours=1)))
        SchedulerLifecycle.prepare()
        SchedulerLifecycle.reconcile_modules({module_name}, ModulesManager.modules)
        ModulesManager.refresh()
        await ModuleStatus.filter(module_name=module_name).delete()
        await ModuleStatus.create(module_name=module_name, load=True)
        with patch.object(ModulesManager, "reload_py_module", side_effect=reload_python):
            async with _patch_database_reload(AsyncMock(return_value=None)):
                success, count = await ModulesManager.reload_module(module_name)

        status = await ModuleStatus.get_or_none(module_name=module_name)
        return (
            not success
            and count == 1
            and ModulesManager.modules.get(module_name) is old_module
            and ModulesManager.modules_aliases.get("__old_database_alias") == module_name
            and "__new_database_alias" not in ModulesManager.modules_aliases
            and ModulesManager.modules_hooks.get(f"{module_name}.reload") is old_hook
            and status is not None
            and status.load
            and SchedulerLifecycle._job_specs[SchedulerLifecycle.module_job_id(module_name, 0)].function is old_schedule
        )
    finally:
        await ModuleStatus.filter(module_name=module_name).delete()
        SchedulerLifecycle._remove_modules({module_name})
        _restore_module_manager(snapshot)


async def _test_reload_failure_restores_entire_python_module_tree():
    """Python 已导入、数据库或其他后置校验失败时也必须恢复旧 sys.modules。"""
    package = "modules.__test_loader_reload_module_tree_rollback"
    module_name = "__test_loader_reload_module_tree_rollback"
    snapshot = _snapshot_module_manager()
    old_python_module = ModuleType(package)
    new_python_module = ModuleType(package)

    async def old_hook():
        return "old-hook"

    async def old_event(_):
        return "old-event"

    async def new_hook():
        return "new-hook"

    async def new_event(_):
        return "new-event"

    def reload_python(_):
        sys.modules[package] = new_python_module
        _reload_test_module(module_name, None, f"{package}.entry", new_hook, new_event)
        return 1

    try:
        old_module = _reload_test_module(module_name, None, f"{package}.entry", old_hook, old_event)
        old_module._db_load = True
        sys.modules[package] = old_python_module
        await ModuleStatus.filter(module_name=module_name).delete()
        await ModuleStatus.create(module_name=module_name, load=True)
        with (
            patch.object(ModulesManager, "reload_py_module", side_effect=reload_python),
            patch.object(ModulesManager, "_model_schema_fingerprint", return_value=()),
        ):
            async with _patch_database_reload(AsyncMock(return_value=None)):
                success, count = await ModulesManager.reload_module(module_name)
        return (
            not success
            and count == 1
            and ModulesManager.modules[module_name] is old_module
            and sys.modules[package] is old_python_module
        )
    finally:
        sys.modules.pop(package, None)
        await ModuleStatus.filter(module_name=module_name).delete()
        _restore_module_manager(snapshot)


async def _test_reload_stops_runtime_before_database_swap():
    """旧 runtime 必须先用旧数据库 context 清理，之后才能切换数据库。"""
    package = "modules.__test_loader_reload_db_order"
    module_name = "__test_loader_reload_db_order"
    snapshot = _snapshot_module_manager()
    order = []

    async def old_hook():
        return "old"

    async def old_event(_):
        return "old"

    async def new_hook():
        return "new"

    async def new_event(_):
        return "new"

    def reload_python(_):
        _reload_test_module(module_name, None, f"{package}.entry", new_hook, new_event)
        return 1

    async def commit_runtime(*_args, **_kwargs):
        order.append("runtime-stop")

    def activate_database(_prepared):
        order.append("database-activate")

    async def close_previous(_prepared):
        order.append("database-close-previous")

    try:
        old_module = _reload_test_module(module_name, None, f"{package}.entry", old_hook, old_event)
        old_module._db_load = True
        await ModuleStatus.filter(module_name=module_name).delete()
        await ModuleStatus.create(module_name=module_name, load=True)
        with (
            patch.object(ModulesManager, "reload_py_module", side_effect=reload_python),
            patch.object(loader_module, "prepare_db_reload", new=AsyncMock(return_value=object())),
            patch.object(loader_module, "activate_db_reload", new=activate_database),
            patch.object(loader_module, "close_previous_db_context", new=close_previous),
            patch.object(loader_module, "close_prepared_db_reload", new=AsyncMock()),
            patch.object(ModuleRuntimeManager, "commit_reload", new=commit_runtime),
        ):
            success, count = await ModulesManager.reload_module(module_name)
        return (
            success
            and count == 1
            and order
            == [
                "runtime-stop",
                "database-activate",
                "database-close-previous",
            ]
        )
    finally:
        await ModuleStatus.filter(module_name=module_name).delete()
        ModuleRuntimeManager._staging.clear()
        ModuleRuntimeManager._reload_created.clear()
        ModuleRuntimeManager._reload_in_progress = False
        _restore_module_manager(snapshot)


def _test_reload_defers_cross_module_bindings():
    """兄弟文件先执行的装饰器须等目标模块重新注册后再绑定。"""
    package = "modules.__test_loader_reload_deferred"
    module_name = "__test_loader_reload_deferred"
    snapshot = _snapshot_module_manager()

    async def deferred_hook():
        return "deferred"

    try:
        ModulesManager._reload_package = package
        ModulesManager._deferred_bindings = []
        meta = HookMeta(function=deferred_hook, name="cross-file")
        ModulesManager.bind_to_module(module_name, meta)
        if ModulesManager._deferred_bindings != [(module_name, meta)]:
            return False
        module = Module.assign(module_name=module_name, alias=None, recommend_modules=None, developers=None)
        ModulesManager.add_module(module, f"{package}.target")
        return module.hooks_list.set == [meta] and not ModulesManager._deferred_bindings
    finally:
        _restore_module_manager(snapshot)


def _test_related_modules_respect_package_boundary():
    """名称互为前缀的包（如 wiki / wikilog）不能被当作同一个热重载范围。"""
    snapshot = _snapshot_module_manager()
    first_name = "__test_loader_package_boundary_first"
    second_name = "__test_loader_package_boundary_second"
    try:
        first = Module.assign(module_name=first_name, alias=None, recommend_modules=None, developers=None)
        second = Module.assign(module_name=second_name, alias=None, recommend_modules=None, developers=None)
        ModulesManager.add_module(first, "modules.__test_loader_package.entry")
        ModulesManager.add_module(second, "modules.__test_loader_package_extra.entry")
        return ModulesManager.search_related_module(first_name) == [first_name]
    finally:
        _restore_module_manager(snapshot)


def _test_reload_dependency_closure_is_dependency_first():
    """重载依赖包时必须先重载依赖，再重载使用它的模块。"""
    with (
        patch.object(ModulesManager, "_rebuild_dependency_graph"),
        patch.dict(
            ModulesManager._dependency_graph,
            {
                "modules.wiki": set(),
                "modules.wikilog": {"modules.wiki"},
                "modules.wiki-audit": {"modules.wiki"},
            },
            clear=True,
        ),
    ):
        closure = ModulesManager._reload_closure("modules.wiki")
    return closure == ["modules.wiki", "modules.wiki-audit", "modules.wikilog"]


def _test_dependency_scan_covers_from_import_and_dynamic_import():
    """依赖图须识别 from modules import 与常量 import_module 调用。"""
    package = "modules.__test_loader_dependency_scan"
    with TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        (root / "entry.py").write_text(
            "\n".join(
                (
                    "from modules import alpha",
                    "import importlib",
                    'importlib.import_module("modules.beta.child")',
                    'importlib.import_module(name="modules.gamma")',
                )
            ),
            encoding="utf-8",
        )
        module = ModuleType(package)
        module.__path__ = [temp_dir]
        module.__file__ = str(root / "__init__.py")
        with patch.dict(sys.modules, {package: module}):
            dependencies = ModulesManager._scan_package_dependencies(package)
    return dependencies == {"modules.alpha", "modules.beta", "modules.gamma"}


def _test_locale_fingerprint_detects_removed_files():
    """删除模块全部 Locale 文件时也必须产生不同指纹。"""
    package = "modules.__test_loader_locale_removal"
    with TemporaryDirectory() as temp_dir:
        module_file = Path(temp_dir) / "__init__.py"
        module_file.write_text("", encoding="utf-8")
        locale_file = Path(temp_dir) / "locales" / "zh_cn.json"
        locale_file.parent.mkdir()
        locale_file.write_text('{"key": "value"}', encoding="utf-8")
        module = ModuleType(package)
        module.__file__ = str(module_file)
        with patch.dict(sys.modules, {package: module}):
            before = ModulesManager._locale_fingerprint(package)
            locale_file.unlink()
            after = ModulesManager._locale_fingerprint(package)
    return bool(before) and after == () and before != after


def _test_reload_syncs_missing_module_config_fields():
    """reload 后新增的模块配置字段应通过授权接口补写。"""
    package = "modules.__test_loader_config_sync"
    config_module_name = f"{package}.config"

    class ProbeConfig:
        __config_fields__ = {
            "probe_value": {
                "default": 42,
                "cfg_type": int,
                "secret": False,
                "table_name": "module_probe",
            }
        }

    config_module = ModuleType(config_module_name)
    config_module.ProbeConfig = ProbeConfig
    edit_write = MagicMock()
    try:
        with (
            patch.dict(sys.modules, {config_module_name: config_module}),
            patch.object(CFGManager, "has", return_value=False),
            patch.object(CFGManager, "edit_write", edit_write),
        ):
            errors = ModulesManager._sync_config_fields(package)
        return not errors and edit_write.call_args_list == [call("probe_value", 42, int, False, "module_probe")]
    finally:
        sys.modules.pop(config_module_name, None)


def _test_schema_fingerprint_covers_schema_attributes():
    """schema 指纹必须覆盖 unique、索引、列名、约束和外键参数。"""

    class ProbeField:
        def __init__(self, **overrides):
            self.metadata = {
                "field_type": "tortoise.fields.data.CharField",
                "db_column": "value",
                "nullable": False,
                "unique": False,
                "indexed": False,
                "constraints": {"max_length": 32},
                "db_field_types": {"": "VARCHAR(32)"},
                "db_default": "NOT_PROVIDED",
            }
            self.metadata.update(overrides)

        def describe(self, serializable=False):
            return dict(self.metadata)

    baseline = ModulesManager._field_schema_fingerprint(ProbeField())
    changes = [
        ProbeField(unique=True),
        ProbeField(indexed=True),
        ProbeField(db_column="renamed"),
        ProbeField(constraints={"max_length": 64}),
        ProbeField(db_default=42),
        ProbeField(on_delete="CASCADE", db_constraint=True),
    ]
    return all(ModulesManager._field_schema_fingerprint(field) != baseline for field in changes)


def _test_reload_py_module_visits_nested_modules_once():
    """隔离重载按原 sys.modules 顺序重新 import 整个模块树。"""
    root_name = "__test_loader_reload_tree"
    module_names = [root_name, f"{root_name}.child", f"{root_name}.child.grandchild", f"{root_name}.sibling"]
    fake_modules = {name: ModuleType(name) for name in module_names}
    reload_order = []

    def import_python(name):
        reload_order.append(name)
        module = fake_modules[name]
        sys.modules[name] = module
        return module

    with (
        patch.dict(sys.modules, fake_modules),
        patch.object(loader_module.importlib, "import_module", side_effect=import_python),
    ):
        count = ModulesManager.reload_py_module(root_name)

    return count == len(module_names) and reload_order == module_names and len(reload_order) == len(set(reload_order))


def _test_reload_py_module_propagates_child_failure():
    """任一子模块失败都须让整个包返回 -999，不能被其它成功计数抵消。"""
    root_name = "__test_loader_reload_failure_tree"
    child_name = f"{root_name}.child"
    fake_modules = {root_name: ModuleType(root_name), child_name: ModuleType(child_name)}
    reload_order = []

    def import_python(name):
        reload_order.append(name)
        if name == child_name:
            raise RuntimeError("child reload failed")
        module = fake_modules[name]
        sys.modules[name] = module
        return module

    with (
        patch.dict(sys.modules, fake_modules),
        patch.object(loader_module.importlib, "import_module", side_effect=import_python),
    ):
        count = ModulesManager.reload_py_module(root_name)
        restored = set(fake_modules) <= set(sys.modules)

    return count == -999 and root_name in reload_order and child_name in reload_order and restored


def _test_reload_py_module_uses_fresh_namespace():
    """重载应替换模块对象，旧函数持有的模块字典不能被原地改写。"""
    module_name = "__test_loader_fresh_namespace"
    old_module = ModuleType(module_name)
    old_module.version = "old"
    new_module = ModuleType(module_name)
    new_module.version = "new"

    def import_python(name):
        sys.modules[name] = new_module
        return new_module

    with (
        patch.dict(sys.modules, {module_name: old_module}),
        patch.object(loader_module.importlib, "import_module", side_effect=import_python),
    ):
        count = ModulesManager.reload_py_module(module_name)
        replaced = sys.modules[module_name] is new_module

    return count == 1 and replaced and old_module.version == "old" and new_module.version == "new"


async def _test_concurrent_reload_fails_before_mutation():
    """第二个模块重载必须立即失败，不能等待锁后与数据库维护流程互锁。"""

    package = "modules.__test_loader_reload_concurrent"
    module_name = "__test_loader_reload_concurrent"
    snapshot = _snapshot_module_manager()
    entered_database_reload = asyncio.Event()
    release_database_reload = asyncio.Event()

    async def prepare_database():
        entered_database_reload.set()
        await release_database_reload.wait()
        return object()

    def reload_python(_):
        module = Module.assign(module_name=module_name, alias=None, recommend_modules=None, developers=None)
        ModulesManager.add_module(module, f"{package}.entry")
        return 1

    reload_py_module = MagicMock(side_effect=reload_python)
    try:
        module = Module.assign(module_name=module_name, alias=None, recommend_modules=None, developers=None)
        ModulesManager.add_module(module, f"{package}.entry")
        await ModuleStatus.filter(module_name=module_name).delete()
        await ModuleStatus.create(module_name=module_name, load=True)
        with patch.object(ModulesManager, "reload_py_module", new=reload_py_module):
            async with _patch_database_reload(prepare_database):
                first = asyncio.create_task(ModulesManager.reload_module(module_name))
                await asyncio.wait_for(entered_database_reload.wait(), timeout=1)
                second_result = await asyncio.wait_for(ModulesManager.reload_module("second"), timeout=1)
                untouched = second_result == (False, 0) and reload_py_module.call_count == 1
                release_database_reload.set()
                first_result = await asyncio.wait_for(first, timeout=1)
        return untouched and first_result == (True, 1)
    finally:
        release_database_reload.set()
        await ModuleStatus.filter(module_name=module_name).delete()
        _restore_module_manager(snapshot)


async def _test_initial_load_rolls_back_partial_registration():
    """启动导入失败时不能留下半注册模块；仅配置模块本身缺失才可忽略。"""
    broken_package = "modules.__test_loader_initial_broken"
    optional_package = "modules.__test_loader_initial_optional"
    broken_name = "__test_loader_initial_broken"
    optional_name = "__test_loader_initial_optional"
    snapshot = _snapshot_module_manager()

    def import_module(name: str):
        if name == broken_package:
            module = Module.assign(module_name=broken_name, alias=None, recommend_modules=None, developers=None)
            ModulesManager.add_module(module, broken_package)
            return ModuleType(name)
        if name == f"{broken_package}.config":
            raise ModuleNotFoundError("No module named 'required_dependency'", name="required_dependency")
        if name == optional_package:
            module = Module.assign(module_name=optional_name, alias=None, recommend_modules=None, developers=None)
            ModulesManager.add_module(module, optional_package)
            return ModuleType(name)
        if name == f"{optional_package}.config":
            raise ModuleNotFoundError(f"No module named '{name}'", name=name)
        raise AssertionError(f"Unexpected import: {name}")

    status_query = MagicMock()
    status_query.values_list = AsyncMock(return_value=[])
    try:
        with TemporaryDirectory() as temp_dir:
            with (
                patch.object(
                    loader_module.pkgutil,
                    "iter_modules",
                    return_value=[
                        SimpleNamespace(name="__test_loader_initial_broken"),
                        SimpleNamespace(name="__test_loader_initial_optional"),
                    ],
                ),
                patch.object(loader_module.importlib, "import_module", side_effect=import_module),
                patch.object(ModuleStatus, "init_modules", new=AsyncMock()),
                patch.object(ModuleStatus, "all", return_value=status_query),
                patch.object(PrivateAssets, "path", Path(temp_dir)),
            ):
                await loader_module.load_modules()
                loader_result = (Path(temp_dir) / ".cache_loader").read_text(encoding="utf-8")

        return (
            broken_name not in ModulesManager.modules
            and optional_name in ModulesManager.modules
            and "required_dependency" in loader_result
            and f"Failed to load {optional_package}" not in loader_result
        )
    finally:
        _restore_module_manager(snapshot)


async def _test_cancelled_reload_restores_registry_and_status():
    """取消已修改状态的热重载时，须恢复旧注册表与持久化启用状态。"""
    package = "modules.__test_loader_reload_cancelled"
    module_name = "__test_loader_reload_cancelled"
    snapshot = _snapshot_module_manager()
    entered_database_reload = asyncio.Event()

    async def old_hook():
        return "old"

    async def old_event(_):
        return "old"

    async def new_hook():
        return "new"

    async def new_event(_):
        return "new"

    def reload_python(_):
        _reload_test_module(module_name, "__cancelled_new", f"{package}.entry", new_hook, new_event)
        return 1

    async def prepare_database():
        entered_database_reload.set()
        await asyncio.Event().wait()

    try:
        old_module = _reload_test_module(
            module_name,
            "__cancelled_old",
            f"{package}.entry",
            old_hook,
            old_event,
        )
        ModulesManager.refresh()
        await ModuleStatus.filter(module_name=module_name).delete()
        await ModuleStatus.create(module_name=module_name, load=False)

        with patch.object(ModulesManager, "reload_py_module", side_effect=reload_python):
            async with _patch_database_reload(prepare_database):
                task = asyncio.create_task(ModulesManager.reload_module(module_name))
                await asyncio.wait_for(entered_database_reload.wait(), timeout=1)
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                else:
                    return False

        status = await ModuleStatus.get_or_none(module_name=module_name)
        return (
            ModulesManager.modules.get(module_name) is old_module
            and ModulesManager.modules_aliases.get("__cancelled_old") == module_name
            and "__cancelled_new" not in ModulesManager.modules_aliases
            and status is not None
            and not status.load
        )
    finally:
        await ModuleStatus.filter(module_name=module_name).delete()
        _restore_module_manager(snapshot)


async def _test_cancelled_commit_keeps_committed_generation():
    """取消发生在 commit 中时，必须等待 commit 完成且不得回滚新代。"""
    package = "modules.__test_loader_reload_commit_cancel"
    module_name = "__test_loader_reload_commit_cancel"
    snapshot = _snapshot_module_manager()
    entered_commit = asyncio.Event()
    release_commit = asyncio.Event()

    async def old_hook():
        return "old"

    async def old_event(_):
        return "old"

    async def new_hook():
        return "new"

    async def new_event(_):
        return "new"

    def reload_python(_):
        _reload_test_module(module_name, "__commit_cancel_new", f"{package}.entry", new_hook, new_event)
        return 1

    async def commit_reload(*_args, **_kwargs):
        entered_commit.set()
        await release_commit.wait()

    try:
        old_module = _reload_test_module(
            module_name,
            "__commit_cancel_old",
            f"{package}.entry",
            old_hook,
            old_event,
        )
        old_module._db_load = True
        ModulesManager.refresh()
        await ModuleStatus.filter(module_name=module_name).delete()
        await ModuleStatus.create(module_name=module_name, load=True)
        with (
            patch.object(ModulesManager, "reload_py_module", side_effect=reload_python),
            patch.object(ModuleRuntimeManager, "commit_reload", new=commit_reload),
        ):
            async with _patch_database_reload(AsyncMock(return_value=object())):
                task = asyncio.create_task(ModulesManager.reload_module(module_name))
                await asyncio.wait_for(entered_commit.wait(), timeout=1)
                task.cancel()
                release_commit.set()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                else:
                    return False

        status = await ModuleStatus.get_or_none(module_name=module_name)
        return (
            ModulesManager.modules.get(module_name) is not old_module
            and ModulesManager.modules_aliases.get("__commit_cancel_new") == module_name
            and "__commit_cancel_old" not in ModulesManager.modules_aliases
            and status is not None
            and status.load
        )
    finally:
        release_commit.set()
        await ModuleStatus.filter(module_name=module_name).delete()
        ModuleRuntimeManager._staging.clear()
        ModuleRuntimeManager._reload_created.clear()
        ModuleRuntimeManager._reload_in_progress = False
        _restore_module_manager(snapshot)


async def _test_load_state_changes_only_after_persistence():
    """全局加载状态持久化失败时，内存标志不能提前翻转。"""
    module_name = "__test_loader_persisted_state"
    snapshot = _snapshot_module_manager()
    try:
        module = Module.assign(module_name=module_name, alias=None, recommend_modules=None, developers=None)
        module._db_load = False
        ModulesManager.add_module(module, "modules.__test_loader_persisted_state")
        with patch.object(
            ModuleStatus,
            "set_module_loaded",
            new=AsyncMock(side_effect=RuntimeError("database unavailable")),
        ):
            try:
                await ModulesManager.load_module(module_name)
            except RuntimeError:
                load_unchanged = not module._db_load
            else:
                return False

        module._db_load = True
        with patch.object(
            ModuleStatus,
            "set_module_loaded",
            new=AsyncMock(side_effect=RuntimeError("database unavailable")),
        ):
            try:
                await ModulesManager.unload_module(module_name)
            except RuntimeError:
                unload_unchanged = module._db_load
            else:
                return False
        return load_unchanged and unload_unchanged
    finally:
        _restore_module_manager(snapshot)


async def _test_unload_drains_queue_before_stopping_runtime():
    """unload 必须排空在途 handler 后，才关闭 Scheduler 与模块 runtime。"""
    module_name = "__test_loader_unload_order"
    snapshot = _snapshot_module_manager()
    order = []

    @asynccontextmanager
    async def queue_window(*, exclusive=True):
        order.append(f"queue:{exclusive}")
        yield

    @asynccontextmanager
    async def scheduler_window(module_names=None):
        order.append(f"scheduler:{tuple(module_names or ())}")
        yield

    async def persist(*_args, **_kwargs):
        order.append("persist")

    async def suspend(name):
        order.append(f"suspend:{name}")

    try:
        module = Module.assign(module_name=module_name, alias=None, recommend_modules=None, developers=None)
        module._db_load = True
        ModulesManager.add_module(module, f"modules.{module_name}")
        with (
            patch.object(JobQueueServer, "maintenance_window", new=queue_window),
            patch.object(SchedulerLifecycle, "maintenance_window", new=scheduler_window),
            patch.object(SchedulerLifecycle, "reconcile_modules", side_effect=lambda *_args: order.append("reconcile")),
            patch.object(ModuleStatus, "set_module_loaded", new=persist),
            patch.object(ModuleRuntimeManager, "suspend", new=suspend),
        ):
            success = await ModulesManager.unload_module(module_name)
        return success and order == [
            "queue:False",
            f"scheduler:('{module_name}',)",
            "persist",
            "reconcile",
            f"suspend:{module_name}",
        ]
    finally:
        _restore_module_manager(snapshot)


@func_case
async def test_loader(tester: Tester):
    """core.loader: 模块加载器测试"""
    await tester.test(_test_add_module, "ModulesManager.add_module 测试")
    await tester.test(_test_add_module_duplicate, "ModulesManager.add_module 重复测试")
    await tester.test(_test_remove_modules, "ModulesManager.remove_modules 测试")
    await tester.test(_test_remove_nonexistent_module, "ModulesManager.remove_modules 不存在测试")
    await tester.test(_test_bind_to_module_command, "ModulesManager.bind_to_module CommandMeta 测试")
    await tester.test(_test_bind_to_module_regex, "ModulesManager.bind_to_module RegexMeta 测试")
    await tester.test(_test_bind_to_nonexistent_module, "ModulesManager.bind_to_module 不存在模块测试")
    await tester.test(_test_return_modules_list, "ModulesManager.return_modules_list 测试")
    await tester.test(_test_return_modules_list_filter_platform, "ModulesManager.return_modules_list 平台过滤测试")
    await tester.test(_test_refresh_aliases, "ModulesManager.refresh_modules_aliases 测试")
    await tester.test(
        _test_get_module_and_alias_first_words,
        "ModulesManager.get_module_and_alias_first_words 测试",
    )
    await tester.test(_test_renamed_modules_keep_legacy_aliases, "模块主名连字符迁移别名测试")
    await tester.test(_test_module_status_alias_migration, "ModuleStatus 旧主名加载状态迁移测试")
    await tester.test(_test_reload_preserves_mixed_status_and_rebuilds_registries, "模块重载保留混合状态与注册表")
    await tester.test(_test_reload_accepts_new_aliasless_module, "模块重载接受无别名的新模块")
    await tester.test(
        _test_reload_drains_queue_before_scheduler_maintenance,
        "模块重载先排空队列再进入 Scheduler 维护",
    )
    await tester.test(_test_reload_python_failure_restores_all_registries, "Python 重载失败恢复完整注册表")
    await tester.test(_test_reload_reports_database_reinitialization_failure, "数据库重载失败恢复旧状态")
    await tester.test(
        _test_reload_failure_restores_entire_python_module_tree,
        "reload 后置失败恢复完整 Python 模块树",
    )
    await tester.test(
        _test_reload_stops_runtime_before_database_swap,
        "reload 先停止旧 runtime 再切换数据库",
    )
    await tester.test(_test_reload_defers_cross_module_bindings, "跨模块装饰器延迟绑定")
    await tester.test(_test_related_modules_respect_package_boundary, "热重载包名前缀边界")
    await tester.test(_test_reload_dependency_closure_is_dependency_first, "热重载依赖闭包顺序")
    await tester.test(
        _test_dependency_scan_covers_from_import_and_dynamic_import,
        "热重载依赖扫描覆盖动态导入形式",
    )
    await tester.test(
        _test_locale_fingerprint_detects_removed_files,
        "热重载检测 Locale 文件删除",
    )
    await tester.test(_test_reload_syncs_missing_module_config_fields, "热重载补写新增配置字段")
    await tester.test(
        _test_schema_fingerprint_covers_schema_attributes,
        "热重载 schema 指纹覆盖结构属性",
    )
    await tester.test(_test_reload_py_module_visits_nested_modules_once, "嵌套 Python 模块只重载一次")
    await tester.test(_test_reload_py_module_propagates_child_failure, "子模块重载失败向上传播")
    await tester.test(_test_reload_py_module_uses_fresh_namespace, "Python 重载使用新模块命名空间")
    await tester.test(_test_concurrent_reload_fails_before_mutation, "并发模块重载在改动前快速失败")
    await tester.test(_test_initial_load_rolls_back_partial_registration, "启动加载失败回滚半注册模块")
    await tester.test(_test_cancelled_reload_restores_registry_and_status, "取消热重载恢复注册表与状态")
    await tester.test(_test_cancelled_commit_keeps_committed_generation, "取消 commit 等待完成且不回滚新代")
    await tester.test(_test_load_state_changes_only_after_persistence, "全局加载状态持久化后更新内存")
    await tester.test(_test_unload_drains_queue_before_stopping_runtime, "unload 先排空 Queue 再停止 runtime")
    return tester
