"""Framework-managed module runtime lifecycle tests."""

import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from core.module_runtime import ModuleRuntimeManager
from core.tester import Tester, func_case


def _reset_runtime_manager():
    ModuleRuntimeManager._current.clear()
    ModuleRuntimeManager._staging.clear()
    ModuleRuntimeManager._reload_created.clear()
    ModuleRuntimeManager._reload_in_progress = False


def _test_state_preserve_reset_and_migrate():
    module_name = "__test_module_runtime_state"

    reset_state = ModuleRuntimeManager.state(module_name, "reset", default_factory=list)
    reset_state.append("old")
    removed_state = ModuleRuntimeManager.state(module_name, "removed", default_factory=list)
    removed_state.append("drop")
    preserved = ModuleRuntimeManager.state(module_name, "preserved", default_factory=list, preserve=True)
    preserved.append("kept")
    versioned = ModuleRuntimeManager.state(
        module_name,
        "versioned",
        default_factory=dict,
        preserve=True,
        version=1,
    )
    versioned["value"] = 1

    runtime = ModuleRuntimeManager._current[module_name]
    next_runtime = runtime.next_generation()
    dropped_removed_state = "removed" not in next_runtime.state

    reset_next = next_runtime.get_state("reset", default_factory=list, preserve=False, version=1, migrate=None)
    preserved_next = next_runtime.get_state(
        "preserved",
        default_factory=list,
        preserve=True,
        version=1,
        migrate=None,
    )
    versioned_next = next_runtime.get_state(
        "versioned",
        default_factory=dict,
        preserve=True,
        version=2,
        migrate=lambda old: {"value": old["value"] + 1},
    )
    return dropped_removed_state and reset_next == [] and preserved_next is preserved and versioned_next == {"value": 2}


def _test_state_migration_does_not_mutate_previous_generation():
    """版本迁移函数只能修改框架提供的副本，失败回滚后旧状态必须保持原样。"""
    module_name = "__test_module_runtime_migrate_copy"
    runtime = ModuleRuntimeManager.get_or_create(module_name)
    original = runtime.get_state(
        "state",
        default_factory=dict,
        preserve=True,
        version=1,
        migrate=None,
    )
    original["value"] = 1
    staged = runtime.next_generation()

    def migrate(previous):
        previous["value"] = 2
        return previous

    migrated = staged.get_state(
        "state",
        default_factory=dict,
        preserve=True,
        version=2,
        migrate=migrate,
    )
    return migrated == {"value": 2} and original == {"value": 1} and migrated is not original


async def _test_resource_is_lazy_and_recreated_after_suspend():
    module_name = "__test_module_runtime_resource"
    closed = []
    created = []

    class Resource:
        pass

    async def factory():
        resource = Resource()
        created.append(resource)
        return resource

    def close(resource):
        closed.append(resource)

    resource = ModuleRuntimeManager.resource(module_name, "resource", factory, close)
    before = not created and not closed
    first = await resource.get()
    await ModuleRuntimeManager.suspend(module_name)
    suspended = closed == [first]
    ModuleRuntimeManager.activate(module_name)
    second = await resource.get()
    return before and suspended and second is not first and created == [first, second]


async def _test_resource_creation_timeout_is_bounded():
    """异步资源工厂超时后不得把半成品标记为已初始化。"""
    module_name = "__test_module_runtime_resource_timeout"

    async def factory():
        await asyncio.Event().wait()

    resource = ModuleRuntimeManager.resource(module_name, "slow", factory, timeout=0.01)
    try:
        await resource.get()
    except TimeoutError:
        timed_out = True
    else:
        timed_out = False
    return timed_out and not resource.initialized and resource.value is None


async def _test_spawned_tasks_are_cancelled_on_stop():
    module_name = "__test_module_runtime_task"
    started = asyncio.Event()
    stopped = asyncio.Event()

    async def worker():
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    task = ModuleRuntimeManager.spawn(module_name, worker(), name="runtime-test-task")
    await asyncio.wait_for(started.wait(), timeout=1)
    await ModuleRuntimeManager.suspend(module_name)
    return task.cancelled() and stopped.is_set() and task not in ModuleRuntimeManager._current[module_name].tasks


async def _test_stop_cancellation_still_closes_remaining_resources():
    """停止流程被取消时仍须继续关闭后续资源，再传播取消。"""
    module_name = "__test_module_runtime_stop_cancelled"
    closed = []
    cleanup_started = asyncio.Event()

    async def cleanup():
        cleanup_started.set()
        await asyncio.Event().wait()

    runtime = ModuleRuntimeManager.get_or_create(module_name)
    first = runtime.declare_resource("first", object, close=lambda value: closed.append("first"), timeout=1)
    second = runtime.declare_resource("second", object, close=lambda value: closed.append("second"), timeout=1)
    await first.get()
    await second.get()
    runtime.declare_cleanup(cleanup, timeout=10)
    stop_task = asyncio.create_task(runtime.stop("cancelled-test"))
    await cleanup_started.wait()
    stop_task.cancel()
    result = (await asyncio.gather(stop_task, return_exceptions=True))[0]
    return isinstance(result, asyncio.CancelledError) and closed == ["second", "first"] and not runtime.active


async def _test_reload_commits_new_generation_and_stops_old():
    module_name = "__test_module_runtime_reload"
    closed = []
    preserved = ModuleRuntimeManager.state(module_name, "state", default_factory=list, preserve=True)
    preserved.append("kept")
    resource = ModuleRuntimeManager.resource(module_name, "resource", object, close=lambda value: closed.append(value))
    old_value = await resource.get()
    old_runtime = ModuleRuntimeManager._current[module_name]

    snapshot = ModuleRuntimeManager.prepare_reload({module_name})
    staged = ModuleRuntimeManager.get_or_create(module_name)
    staged_inactive = not staged.active
    spawn_rejected = False
    coroutine = asyncio.sleep(0)
    try:
        staged.spawn(coroutine)
    except RuntimeError:
        spawn_rejected = True
        coroutine.close()
    staged_state = staged.get_state("state", default_factory=list, preserve=True, version=1, migrate=None)
    staged_resource = staged.declare_resource("resource", object, lambda value: None, timeout=10)
    await ModuleRuntimeManager.commit_reload(snapshot, {module_name}, {module_name})

    current = ModuleRuntimeManager._current[module_name]
    new_value = await staged_resource.get()
    return (
        current.generation == old_runtime.generation + 1
        and staged_state is preserved
        and closed == [old_value]
        and new_value is not old_value
        and current.active
        and staged_inactive
        and spawn_rejected
    )


async def _test_reload_abort_keeps_old_generation():
    module_name = "__test_module_runtime_abort"
    closed = []
    resource = ModuleRuntimeManager.resource(module_name, "resource", object, close=lambda value: closed.append(value))
    value = await resource.get()
    old_runtime = ModuleRuntimeManager._current[module_name]

    snapshot = ModuleRuntimeManager.prepare_reload({module_name})
    staged = ModuleRuntimeManager.get_or_create(module_name)
    await ModuleRuntimeManager.abort_reload(snapshot, {module_name})

    return (
        ModuleRuntimeManager._current[module_name] is old_runtime
        and not closed
        and staged is not old_runtime
        and not staged.active
        and value is not None
    )


async def _test_cache_paths_rotate_after_reload():
    """版本化缓存目录只在新 generation 提交后清理旧版本。"""
    module_name = "__test_module_runtime_cache_path"
    with TemporaryDirectory() as temp_dir:
        with patch("core.module_runtime.cache_path", Path(temp_dir)):
            old_runtime = ModuleRuntimeManager.get_or_create(module_name)
            old_path = old_runtime.declare_cache_path("data", 1)
            (old_path / "value.txt").write_text("old", encoding="utf-8")
            snapshot = ModuleRuntimeManager.prepare_reload({module_name})
            staged = ModuleRuntimeManager.get_or_create(module_name)
            new_path = staged.declare_cache_path("data", 2)
            (new_path / "value.txt").write_text("new", encoding="utf-8")
            await ModuleRuntimeManager.commit_reload(snapshot, {module_name}, {module_name})
            return not old_path.exists() and new_path.exists() and (new_path / "value.txt").read_text() == "new"


async def _test_aborted_reload_preserves_shared_cache_path():
    """失败重载不得删除与旧 generation 共用的缓存目录。"""
    module_name = "__test_module_runtime_shared_cache_path"
    with TemporaryDirectory() as temp_dir:
        with patch("core.module_runtime.cache_path", Path(temp_dir)):
            old_runtime = ModuleRuntimeManager.get_or_create(module_name)
            old_path = old_runtime.declare_cache_path("data", 1)
            (old_path / "value.txt").write_text("old", encoding="utf-8")
            snapshot = ModuleRuntimeManager.prepare_reload({module_name})
            staged = ModuleRuntimeManager.get_or_create(module_name)
            staged_path = staged.declare_cache_path("data", 1)
            await ModuleRuntimeManager.abort_reload(snapshot, {module_name})
            return (
                staged_path == old_path
                and old_path.exists()
                and (old_path / "value.txt").read_text(encoding="utf-8") == "old"
            )


async def _test_unregistered_runtime_created_during_reload_is_rolled_back():
    """导入期间意外创建的 runtime 也必须保持 inactive，并在失败时移除。"""
    module_name = "__test_module_runtime_unregistered"
    snapshot = ModuleRuntimeManager.prepare_reload(set())
    runtime = ModuleRuntimeManager.get_or_create(module_name)
    tracked = module_name in ModuleRuntimeManager._reload_created
    await ModuleRuntimeManager.abort_reload(snapshot, set())
    return tracked and not runtime.active and module_name not in ModuleRuntimeManager._current


async def _test_removed_module_runtime_is_pruned_after_reload():
    """代码删除模块后，旧 runtime 不得继续滞留在 Manager 中。"""
    module_name = "__test_module_runtime_removed"
    closed = []
    resource = ModuleRuntimeManager.resource(module_name, "resource", object, close=lambda value: closed.append(value))
    old_value = await resource.get()
    snapshot = ModuleRuntimeManager.prepare_reload({module_name})
    staged = ModuleRuntimeManager.get_or_create(module_name)
    await ModuleRuntimeManager.commit_reload(snapshot, {module_name}, set(), registered_modules=set())
    return (
        module_name not in ModuleRuntimeManager._current
        and not staged.active
        and closed == [old_value]
        and not ModuleRuntimeManager._reload_in_progress
    )


@func_case
async def test_module_runtime(tester: Tester):
    """模块 runtime 状态、资源、任务与 generation 切换。"""
    try:
        await tester.test(_test_state_preserve_reset_and_migrate, "状态重置、保留与版本迁移")
        await tester.test(
            _test_state_migration_does_not_mutate_previous_generation,
            "状态迁移不得污染旧 generation",
        )
        await tester.test(_test_resource_is_lazy_and_recreated_after_suspend, "资源惰性创建与停用后重建")
        await tester.test(_test_resource_creation_timeout_is_bounded, "资源创建超时受框架约束")
        await tester.test(_test_spawned_tasks_are_cancelled_on_stop, "托管后台任务随 runtime 取消")
        await tester.test(
            _test_stop_cancellation_still_closes_remaining_resources,
            "runtime 停止被取消时继续清理资源",
        )
        await tester.test(_test_reload_commits_new_generation_and_stops_old, "reload 提交新 generation 并停止旧代")
        await tester.test(_test_reload_abort_keeps_old_generation, "reload 中止保留旧 generation")
        await tester.test(_test_cache_paths_rotate_after_reload, "reload 提交后轮换模块缓存目录")
        await tester.test(_test_aborted_reload_preserves_shared_cache_path, "reload 中止保留共享缓存目录")
        await tester.test(
            _test_unregistered_runtime_created_during_reload_is_rolled_back,
            "reload 导入期的未注册 runtime 失败回滚",
        )
        await tester.test(
            _test_removed_module_runtime_is_pruned_after_reload,
            "reload 删除模块后清理旧 runtime",
        )
    finally:
        await ModuleRuntimeManager.shutdown()
        _reset_runtime_manager()
    return tester
