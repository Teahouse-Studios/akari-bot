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


def _test_state_preserve_reset_and_migrate():
    module_name = "__test_module_runtime_state"

    reset_state = ModuleRuntimeManager.state(module_name, "reset", default_factory=list)
    reset_state.append("old")
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
    return reset_next == [] and preserved_next is preserved and versioned_next == {"value": 2}


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
    staged_state = staged.get_state("state", default_factory=list, preserve=True, version=1, migrate=None)
    staged_resource = staged.declare_resource("resource", object, lambda value: None, timeout=10)
    await staged_resource.get()
    await ModuleRuntimeManager.commit_reload(snapshot, {module_name}, {module_name})

    current = ModuleRuntimeManager._current[module_name]
    return current.generation == old_runtime.generation + 1 and staged_state is preserved and closed == [old_value]


async def _test_reload_abort_keeps_old_generation():
    module_name = "__test_module_runtime_abort"
    closed = []
    resource = ModuleRuntimeManager.resource(module_name, "resource", object, close=lambda value: closed.append(value))
    value = await resource.get()
    old_runtime = ModuleRuntimeManager._current[module_name]

    snapshot = ModuleRuntimeManager.prepare_reload({module_name})
    staged = ModuleRuntimeManager.get_or_create(module_name)
    ModuleRuntimeManager.abort_reload(snapshot, {module_name})

    return (
        ModuleRuntimeManager._current[module_name] is old_runtime
        and not closed
        and staged is not old_runtime
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


@func_case
async def test_module_runtime(tester: Tester):
    """模块 runtime 状态、资源、任务与 generation 切换。"""
    try:
        await tester.test(_test_state_preserve_reset_and_migrate, "状态重置、保留与版本迁移")
        await tester.test(_test_resource_is_lazy_and_recreated_after_suspend, "资源惰性创建与停用后重建")
        await tester.test(_test_spawned_tasks_are_cancelled_on_stop, "托管后台任务随 runtime 取消")
        await tester.test(_test_reload_commits_new_generation_and_stops_old, "reload 提交新 generation 并停止旧代")
        await tester.test(_test_reload_abort_keeps_old_generation, "reload 中止保留旧 generation")
        await tester.test(_test_cache_paths_rotate_after_reload, "reload 提交后轮换模块缓存目录")
    finally:
        await ModuleRuntimeManager.shutdown()
        _reset_runtime_manager()
    return tester
