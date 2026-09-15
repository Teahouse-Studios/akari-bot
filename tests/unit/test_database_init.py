"""数据库连接参数与初始化职责单元测试。"""

import asyncio
from types import SimpleNamespace
from urllib.parse import parse_qs, parse_qsl, urlsplit
from unittest.mock import AsyncMock, patch

import core.database as database
import tortoise.context as tortoise_context
from core.database.models import JobQueuesTable
from core.database.link import prepare_db_link
from core.queue.server import JobQueueServer
from core.queue.transport import PROTOCOL_VERSION
from core.scheduler import Scheduler, SchedulerLifecycle
from core.tester import Tester, func_case
from core.types import Module
from core.types.module.component_meta import ScheduleMeta
from tortoise.context import TortoiseContext

from apscheduler.triggers.interval import IntervalTrigger


def _query_fields(link: str) -> dict[str, list[str]]:
    return parse_qs(urlsplit(link).query)


def _test_sqlite_defaults_are_added():
    link = prepare_db_link("sqlite://database/save.db")
    fields = _query_fields(link)
    keys = [key for key, _ in parse_qsl(urlsplit(link).query)]
    return (
        fields.get("journal_mode") == ["WAL"]
        and fields.get("busy_timeout") == ["30000"]
        and keys.index("busy_timeout") < keys.index("journal_mode")
    )


def _test_sqlite_explicit_fields_are_preserved():
    link = prepare_db_link("sqlite://database/save.db?journal_mode=DELETE&cache_size=2000&busy_timeout=1000")
    fields = _query_fields(link)
    keys = [key for key, _ in parse_qsl(urlsplit(link).query)]
    return (
        fields.get("busy_timeout") == ["1000"]
        and fields.get("journal_mode") == ["DELETE"]
        and fields.get("cache_size") == ["2000"]
        and keys.index("busy_timeout") < keys.index("journal_mode")
    )


def _test_non_sqlite_link_keeps_existing_behavior():
    link = prepare_db_link("mysql+asyncmy://user:pass@localhost/akari?charset=utf8mb4")
    return link == "mysql://user:pass@localhost/akari?charset=utf8mb4"


def _test_module_database_discovery_distinguishes_missing_dependency():
    """没有 models.py 可忽略，但 database 包内部缺依赖必须中止初始化。"""
    module = SimpleNamespace(name="__test_database_discovery")
    with (
        patch.object(database.pkgutil, "iter_modules", return_value=[module]),
        patch.object(database.importlib.util, "find_spec", return_value=None),
    ):
        missing_models_ignored = database.fetch_module_db() == []

    dependency_error = ModuleNotFoundError("No module named 'database_driver'", name="database_driver")
    with (
        patch.object(database.pkgutil, "iter_modules", return_value=[module]),
        patch.object(database.importlib.util, "find_spec", side_effect=dependency_error),
    ):
        try:
            database.fetch_module_db()
        except ModuleNotFoundError as e:
            dependency_propagated = e.name == "database_driver"
        else:
            dependency_propagated = False
    return missing_models_ignored and dependency_propagated


async def _test_runtime_init_does_not_generate_schemas():
    init = AsyncMock()
    generate_schemas = AsyncMock()
    old_database_list = database.Temp.data.get("modules_db_list")
    try:
        with (
            patch.object(database, "fetch_module_db", return_value=["modules.example.database.models"]),
            patch.object(database, "get_db_link", return_value="sqlite://database/save.db"),
            patch.object(database.Tortoise, "init", new=init),
            patch.object(database.Tortoise, "generate_schemas", new=generate_schemas),
        ):
            result = await database.init_db()

        config = init.await_args.kwargs["config"]
        return (
            result
            and generate_schemas.await_count == 0
            and config["apps"]["models"]["models"] == ["core.database.models", "modules.example.database.models"]
            and _query_fields(config["connections"]["local"]).get("busy_timeout") == ["30000"]
        )
    finally:
        if old_database_list is None:
            database.Temp.data.pop("modules_db_list", None)
        else:
            database.Temp.data["modules_db_list"] = old_database_list


async def _test_pre_init_mode_generates_all_schemas():
    init = AsyncMock()
    generate_schemas = AsyncMock()
    old_database_list = database.Temp.data.get("modules_db_list")
    try:
        with (
            patch.object(database, "fetch_module_db", return_value=["modules.example.database.models"]),
            patch.object(database.Tortoise, "init", new=init),
            patch.object(database.Tortoise, "generate_schemas", new=generate_schemas),
        ):
            result = await database.init_db(generate_schemas=True)

        config = init.await_args.kwargs["config"]
        return (
            result
            and generate_schemas.await_count == 1
            and generate_schemas.await_args.kwargs == {"safe": True}
            and "modules.example.database.models" in config["apps"]["models"]["models"]
            and config["apps"]["local_models"]["models"] == ["core.database.local"]
        )
    finally:
        if old_database_list is None:
            database.Temp.data.pop("modules_db_list", None)
        else:
            database.Temp.data["modules_db_list"] = old_database_list


async def _test_failed_init_closes_partial_connections():
    """Tortoise 初始化失败时须清理已经建立的部分连接，保证后续可重试。"""
    close_connections = AsyncMock()
    old_database_list = database.Temp.data.get("modules_db_list")
    try:
        with (
            patch.object(database, "fetch_module_db", return_value=[]),
            patch.object(database.Tortoise, "init", new=AsyncMock(side_effect=RuntimeError("partial init"))),
            patch.object(database.Tortoise, "close_connections", new=close_connections),
        ):
            result = await database.init_db()
        return result is False and close_connections.await_count == 1
    finally:
        if old_database_list is None:
            database.Temp.data.pop("modules_db_list", None)
        else:
            database.Temp.data["modules_db_list"] = old_database_list


async def _test_cancelled_init_closes_partial_connections():
    """数据库初始化被取消时也须清理部分连接，并向上保留取消语义。"""
    entered = asyncio.Event()
    close_connections = AsyncMock()

    async def initialize(**kwargs):
        entered.set()
        await asyncio.Event().wait()

    with (
        patch.object(database, "fetch_module_db", return_value=[]),
        patch.object(database.Tortoise, "init", new=initialize),
        patch.object(database.Tortoise, "close_connections", new=close_connections),
    ):
        task = asyncio.create_task(database.init_db())
        await asyncio.wait_for(entered.wait(), timeout=1)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            return close_connections.await_count == 1
    return False


async def _test_init_db_clears_task_local_tortoise_context():
    """Server 启动后任务应继承空 context，统一走可替换的 global fallback。"""
    context = TortoiseContext()
    context.__enter__()
    old_modules_db_list = database.Temp.data.get("modules_db_list")
    try:
        with (
            patch.object(database, "fetch_module_db", return_value=[]),
            patch.object(database.Tortoise, "init", new=AsyncMock(return_value=context)),
        ):
            result = await database.init_db()
        return result and tortoise_context._current_context.get() is None and context._token is None
    finally:
        if context._token is not None:
            context.__exit__(None, None, None)
        if old_modules_db_list is None:
            database.Temp.data.pop("modules_db_list", None)
        else:
            database.Temp.data["modules_db_list"] = old_modules_db_list


async def _test_activate_db_reload_clears_inherited_old_context():
    """发布新数据库时不得继续把旧 context 固定到 reload 任务。"""
    old_context = TortoiseContext()
    new_context = TortoiseContext()
    previous_global = tortoise_context._global_context
    token = tortoise_context._current_context.set(old_context)
    prepared = database.PreparedDatabaseReload(
        context=new_context,
        previous_context=old_context,
        database_list=[],
    )
    try:
        database.activate_db_reload(prepared)
        return (
            prepared.activated
            and tortoise_context._global_context is new_context
            and tortoise_context._current_context.get() is None
        )
    finally:
        tortoise_context._global_context = previous_global
        tortoise_context._current_context.reset(token)


async def _test_task_created_after_init_uses_replaceable_global_context():
    """初始化后创建的任务不得复制旧 context，必须动态读取 global fallback。"""
    old_context = TortoiseContext()
    new_context = TortoiseContext()
    previous_global = tortoise_context._global_context
    token = tortoise_context._current_context.set(None)
    tortoise_context._global_context = old_context
    release = asyncio.Event()
    started = asyncio.Event()

    async def child():
        inherited = tortoise_context._current_context.get()
        started.set()
        await release.wait()
        return inherited, tortoise_context.get_current_context()

    task = asyncio.create_task(child())
    prepared = database.PreparedDatabaseReload(
        context=new_context,
        previous_context=old_context,
        database_list=[],
    )
    try:
        await started.wait()
        database.activate_db_reload(prepared)
        release.set()
        inherited, resolved = await task
        return inherited is None and resolved is new_context
    finally:
        release.set()
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        tortoise_context._global_context = previous_global
        tortoise_context._current_context.reset(token)


async def _test_reload_activates_prepared_context_before_closing_previous():
    """热重载必须先完整构建新 context，再原子激活并关闭旧 context。"""
    old_modules_db_list = database.Temp.data.get("modules_db_list")
    prepared = object()
    calls = []

    async def prepare(models):
        calls.append(("prepare", models))
        return prepared

    def activate(value):
        calls.append(("activate", value))

    async def close_previous(value):
        calls.append(("close_previous", value))

    try:
        with (
            patch.object(database, "prepare_db_reload", new=prepare),
            patch.object(database, "activate_db_reload", new=activate),
            patch.object(database, "close_previous_db_context", new=close_previous),
        ):
            result = await database.reload_db(db_models=["modules.example.database.models"])
        return result is True and calls == [
            ("prepare", ["modules.example.database.models"]),
            ("activate", prepared),
            ("close_previous", prepared),
        ]
    finally:
        if old_modules_db_list is None:
            database.Temp.data.pop("modules_db_list", None)
        else:
            database.Temp.data["modules_db_list"] = old_modules_db_list


async def _test_reload_failure_does_not_activate_partial_context():
    """新 context 准备失败时旧数据库必须保持激活且不得发布半成品。"""
    old_modules_db_list = database.Temp.data.get("modules_db_list")
    calls = []

    async def prepare(models):
        calls.append(("prepare", models))
        return None

    def activate(value):
        calls.append(("activate", value))

    async def close_previous(value):
        calls.append(("close_previous", value))

    try:
        with (
            patch.object(database, "prepare_db_reload", new=prepare),
            patch.object(database, "activate_db_reload", new=activate),
            patch.object(database, "close_previous_db_context", new=close_previous),
        ):
            result = await database.reload_db(db_models=["modules.broken.database.models"])
        return result is False and calls == [
            ("prepare", ["modules.broken.database.models"]),
        ]
    finally:
        if old_modules_db_list is None:
            database.Temp.data.pop("modules_db_list", None)
        else:
            database.Temp.data["modules_db_list"] = old_modules_db_list


async def _test_reload_waits_for_other_queue_handlers():
    """热重载不能在其它 action 使用 ORM 时关闭数据库连接。"""
    old_modules_db_list = database.Temp.data.get("modules_db_list")
    started = asyncio.Event()
    release = asyncio.Event()
    prepare_called = asyncio.Event()

    async def handler():
        started.set()
        await release.wait()

    async def prepare(models):
        prepare_called.set()
        return object()

    handler_task = asyncio.create_task(handler(), name="test-database-reload-handler")
    JobQueueServer._process_tasks.add(handler_task)
    await asyncio.wait_for(started.wait(), timeout=1)
    try:
        with (
            patch.object(database, "prepare_db_reload", new=prepare),
            patch.object(database, "activate_db_reload"),
            patch.object(database, "close_previous_db_context", new=AsyncMock()),
        ):
            reload_task = asyncio.create_task(database.reload_db())
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            waited = not prepare_called.is_set() and not reload_task.done()
            release.set()
            await handler_task
            result = await asyncio.wait_for(reload_task, timeout=1)
        return waited and result is True and prepare_called.is_set()
    finally:
        release.set()
        if not handler_task.done():
            handler_task.cancel()
        await asyncio.gather(handler_task, return_exceptions=True)
        JobQueueServer._process_tasks.discard(handler_task)
        if old_modules_db_list is None:
            database.Temp.data.pop("modules_db_list", None)
        else:
            database.Temp.data["modules_db_list"] = old_modules_db_list


async def _test_reload_cancels_scheduler_jobs_before_closing_connections():
    """数据库重载须先等待 schedule 的取消清理，再准备新 context。"""
    module_name = "__test_database_scheduler_maintenance"
    started = asyncio.Event()
    stopped = asyncio.Event()
    prepare_saw_stopped = []

    async def scheduled():
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    async def prepare(models):
        prepare_saw_stopped.append(stopped.is_set())
        return object()

    module = Module.assign(module_name=module_name, alias=None, recommend_modules=None, developers=None)
    module._db_load = True
    module.schedule_list.add(ScheduleMeta(function=scheduled, trigger=IntervalTrigger(hours=1)))
    SchedulerLifecycle.prepare()
    SchedulerLifecycle.reconcile_modules({module_name}, {module_name: module})
    job = Scheduler.get_job(SchedulerLifecycle.module_job_id(module_name, 0))
    task = asyncio.create_task(job.func())
    try:
        await asyncio.wait_for(started.wait(), timeout=1)
        with (
            patch.object(database, "prepare_db_reload", new=prepare),
            patch.object(database, "activate_db_reload"),
            patch.object(database, "close_previous_db_context", new=AsyncMock()),
        ):
            result = await database.reload_db()
        return result is True and stopped.is_set() and task.done() and prepare_saw_stopped == [True]
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        SchedulerLifecycle._remove_modules({module_name})


async def _test_reload_keeps_pumping_remote_results():
    """热重载暂停领取时仍须回收远端结果，否则等待回包的 action 会与重载互锁。"""
    old_modules_db_list = database.Temp.data.get("modules_db_list")
    old_is_running = JobQueueServer.is_running
    result_task_id = await JobQueuesTable.add_task("QUEUE-REMOTE", "reload-result", {})
    result_task_id = str(result_task_id)
    await JobQueuesTable.filter(task_id=result_task_id).update(
        status="done", result={"rpc": PROTOCOL_VERSION, "value": {"ready": True}}
    )
    handler_done = asyncio.Event()

    waiter = asyncio.get_running_loop().create_future()
    JobQueueServer._pending[result_task_id] = waiter

    async def handler():
        result = await waiter
        if result.envelope == {"rpc": PROTOCOL_VERSION, "value": {"ready": True}}:
            handler_done.set()

    async def prepare(models):
        return object()

    handler_task = asyncio.create_task(handler(), name="test-database-reload-remote-waiter")
    JobQueueServer._process_tasks.add(handler_task)

    reload_task = None
    poller_task = None
    try:
        JobQueueServer.is_running = False
        JobQueueServer.pause_event.set()
        with (
            patch.object(database, "prepare_db_reload", new=prepare),
            patch.object(database, "activate_db_reload"),
            patch.object(database, "close_previous_db_context", new=AsyncMock()),
        ):
            reload_task = asyncio.create_task(database.reload_db())
            while JobQueueServer.pause_event.is_set() and not reload_task.done():
                await asyncio.sleep(0)
            if reload_task.done():
                return False

            poller_task = asyncio.create_task(
                JobQueueServer.check_job_queue(),
                name="test-database-reload-result-poller",
            )
            result = await asyncio.wait_for(reload_task, timeout=1)
            await asyncio.wait_for(handler_done.wait(), timeout=1)
            return result is True and handler_task.done()
    finally:
        if reload_task is not None and not reload_task.done():
            reload_task.cancel()
        if poller_task is not None and not poller_task.done():
            poller_task.cancel()
        await asyncio.gather(
            *(task for task in (reload_task, poller_task, handler_task) if task is not None),
            return_exceptions=True,
        )
        JobQueueServer._process_tasks.discard(handler_task)
        JobQueueServer._pending.pop(result_task_id, None)
        await JobQueuesTable.filter(task_id=result_task_id).delete()
        JobQueueServer.pause_event.set()
        JobQueueServer.is_running = old_is_running
        if old_modules_db_list is None:
            database.Temp.data.pop("modules_db_list", None)
        else:
            database.Temp.data["modules_db_list"] = old_modules_db_list


async def _test_cancelled_reload_does_not_publish_partial_context():
    """准备新 context 时被取消，不得激活或关闭旧数据库 context。"""
    old_modules_db_list = database.Temp.data.get("modules_db_list")
    entered = asyncio.Event()
    calls = []

    async def prepare(models):
        calls.append(("prepare", models))
        entered.set()
        await asyncio.Event().wait()

    def activate(value):
        calls.append(("activate", value))

    async def close_previous(value):
        calls.append(("close_previous", value))

    try:
        with (
            patch.object(database, "prepare_db_reload", new=prepare),
            patch.object(database, "activate_db_reload", new=activate),
            patch.object(database, "close_previous_db_context", new=close_previous),
        ):
            task = asyncio.create_task(database.reload_db(db_models=["modules.cancelled.database.models"]))
            await asyncio.wait_for(entered.wait(), timeout=1)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                cancelled = True
            else:
                cancelled = False

        return (
            cancelled
            and calls
            == [
                ("prepare", ["modules.cancelled.database.models"]),
            ]
            and JobQueueServer.pause_event.is_set()
        )
    finally:
        if old_modules_db_list is None:
            database.Temp.data.pop("modules_db_list", None)
        else:
            database.Temp.data["modules_db_list"] = old_modules_db_list


@func_case
async def test_database_init(tester: Tester):
    """SQLite 参数自动补全，且仅 pre-init 模式执行建表。"""
    await tester.test(_test_sqlite_defaults_are_added, "SQLite 缺失参数自动补全")
    await tester.test(_test_sqlite_explicit_fields_are_preserved, "SQLite 显式参数保持不变")
    await tester.test(_test_non_sqlite_link_keeps_existing_behavior, "非 SQLite 连接保持现有行为")
    await tester.test(
        _test_module_database_discovery_distinguishes_missing_dependency,
        "模块数据库发现区分缺失 models 与内部依赖",
    )
    await tester.test(_test_runtime_init_does_not_generate_schemas, "运行期初始化不执行建表")
    await tester.test(_test_pre_init_mode_generates_all_schemas, "pre-init 建立核心、local 与模块表")
    await tester.test(_test_failed_init_closes_partial_connections, "数据库初始化失败清理部分连接")
    await tester.test(_test_cancelled_init_closes_partial_connections, "数据库初始化取消清理部分连接")
    await tester.test(_test_init_db_clears_task_local_tortoise_context, "数据库初始化清理任务级 context")
    await tester.test(
        _test_activate_db_reload_clears_inherited_old_context,
        "数据库切换不继承旧任务级 context",
    )
    await tester.test(
        _test_task_created_after_init_uses_replaceable_global_context,
        "初始化后任务使用可替换 global context",
    )
    await tester.test(
        _test_reload_activates_prepared_context_before_closing_previous,
        "热重载先准备新 context 再原子切换",
    )
    await tester.test(_test_reload_failure_does_not_activate_partial_context, "热重载失败不发布半成品 context")
    await tester.test(_test_reload_waits_for_other_queue_handlers, "热重载等待其它队列处理器")
    await tester.test(_test_reload_cancels_scheduler_jobs_before_closing_connections, "热重载先排空计划任务")
    await tester.test(_test_reload_keeps_pumping_remote_results, "热重载暂停时继续回收远端结果")
    await tester.test(
        _test_cancelled_reload_does_not_publish_partial_context,
        "数据库热重载取消不发布半成品 context",
    )
    return tester
