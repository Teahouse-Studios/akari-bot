"""core.loader 模块加载器单元测试。"""

import asyncio
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from types import ModuleType
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from apscheduler.triggers.interval import IntervalTrigger

import core.loader as loader_module
from core.constants import PrivateAssets
from core.database.models import ModuleStatus
from core.loader import ModulesManager
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

        with (
            patch.object(ModulesManager, "reload_py_module", side_effect=reload_python),
            patch.object(loader_module, "reload_db", new=AsyncMock(return_value=True)),
        ):
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

    reload_database = AsyncMock(return_value=True)
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

        with (
            patch.object(ModulesManager, "reload_py_module", side_effect=reload_python),
            patch.object(loader_module, "reload_db", new=reload_database),
        ):
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
            and reload_database.await_count == 0
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
        with (
            patch.object(ModulesManager, "reload_py_module", side_effect=reload_python),
            patch.object(loader_module, "reload_db", new=AsyncMock(return_value=False)),
        ):
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


def _test_reload_py_module_visits_nested_modules_once():
    """递归重载只遍历直接子级，嵌套模块不能被祖先和父级重复执行。"""
    root_name = "__test_loader_reload_tree"
    module_names = [root_name, f"{root_name}.child", f"{root_name}.child.grandchild", f"{root_name}.sibling"]
    fake_modules = {name: ModuleType(name) for name in module_names}
    reload_order = []

    def reload_python(module):
        reload_order.append(module.__name__)
        return module

    with (
        patch.dict(sys.modules, fake_modules),
        patch.object(loader_module.importlib, "reload", side_effect=reload_python),
    ):
        count = ModulesManager.reload_py_module(root_name)

    return (
        count == len(module_names)
        and reload_order == [f"{root_name}.child.grandchild", f"{root_name}.child", f"{root_name}.sibling", root_name]
        and len(reload_order) == len(set(reload_order))
    )


def _test_reload_py_module_propagates_child_failure():
    """任一子模块失败都须让整个包返回 -999，不能被其它成功计数抵消。"""
    root_name = "__test_loader_reload_failure_tree"
    child_name = f"{root_name}.child"
    fake_modules = {root_name: ModuleType(root_name), child_name: ModuleType(child_name)}
    reload_order = []

    def reload_python(module):
        reload_order.append(module.__name__)
        if module.__name__ == child_name:
            raise RuntimeError("child reload failed")
        return module

    with (
        patch.dict(sys.modules, fake_modules),
        patch.object(loader_module.importlib, "reload", side_effect=reload_python),
    ):
        count = ModulesManager.reload_py_module(root_name)

    return count == -999 and reload_order == [child_name]


async def _test_concurrent_reload_fails_before_mutation():
    """第二个模块重载必须立即失败，不能等待锁后与数据库维护流程互锁。"""

    package = "modules.__test_loader_reload_concurrent"
    module_name = "__test_loader_reload_concurrent"
    snapshot = _snapshot_module_manager()
    entered_database_reload = asyncio.Event()
    release_database_reload = asyncio.Event()

    async def reload_database():
        entered_database_reload.set()
        await release_database_reload.wait()
        return True

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
        with (
            patch.object(ModulesManager, "reload_py_module", new=reload_py_module),
            patch.object(loader_module, "reload_db", new=reload_database),
        ):
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

    async def reload_database():
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

        with (
            patch.object(ModulesManager, "reload_py_module", side_effect=reload_python),
            patch.object(loader_module, "reload_db", new=reload_database),
        ):
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
    await tester.test(_test_reload_python_failure_restores_all_registries, "Python 重载失败恢复完整注册表")
    await tester.test(_test_reload_reports_database_reinitialization_failure, "数据库重载失败恢复旧状态")
    await tester.test(_test_reload_defers_cross_module_bindings, "跨模块装饰器延迟绑定")
    await tester.test(_test_related_modules_respect_package_boundary, "热重载包名前缀边界")
    await tester.test(_test_reload_py_module_visits_nested_modules_once, "嵌套 Python 模块只重载一次")
    await tester.test(_test_reload_py_module_propagates_child_failure, "子模块重载失败向上传播")
    await tester.test(_test_concurrent_reload_fails_before_mutation, "并发模块重载在改动前快速失败")
    await tester.test(_test_initial_load_rolls_back_partial_registration, "启动加载失败回滚半注册模块")
    await tester.test(_test_cancelled_reload_restores_registry_and_status, "取消热重载恢复注册表与状态")
    await tester.test(_test_load_state_changes_only_after_persistence, "全局加载状态持久化后更新内存")
    return tester
