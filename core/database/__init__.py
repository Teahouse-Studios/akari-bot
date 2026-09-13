import asyncio
import importlib.util
import inspect
import pkgutil
import traceback
from dataclasses import dataclass
from typing import Any

from tortoise import Tortoise
from tortoise.context import TortoiseContext

from core.builtins.temp import Temp
from core.logger import Logger
from .link import get_db_link, prepare_db_link
from .local import DB_LINK
from .models import DBModel

_reload_lock = asyncio.Lock()


@dataclass(slots=True)
class PreparedDatabaseReload:
    """A fully initialized database context waiting for atomic activation."""

    context: TortoiseContext
    previous_context: TortoiseContext | None
    database_list: list[str]
    activated: bool = False


def fetch_module_db():
    import modules

    database_list = []
    for m in pkgutil.iter_modules(modules.__path__):
        models_module = f"modules.{m.name}.database.models"
        try:
            spec = importlib.util.find_spec(models_module)
            if spec is not None:
                database_list.append(spec.name)
        except ModuleNotFoundError as e:
            # database 包或 models.py 本身不存在是正常情况；但其 __init__.py
            # 内部缺少依赖时必须让 init_db() 失败，不能静默漏挂该模块的数据表。
            if e.name not in {f"modules.{m.name}.database", models_module}:
                raise
        except Exception:
            Logger.exception(traceback.format_exc())
            raise

    Logger.debug(f"Database list: {database_list}")
    return database_list


def get_model_names(models_path: list[str]) -> list[str]:
    table_names = []
    for p in models_path:
        m = importlib.import_module(p)
        for _, obj in inspect.getmembers(m, inspect.isclass):
            if issubclass(obj, DBModel) and obj is not DBModel:
                meta = getattr(obj, "Meta", None)
                if meta and hasattr(meta, "table"):
                    table_names.append(meta.table)

    return table_names


def get_model_fields(models_path: list[str], table_name: str) -> list[dict[str, Any]]:
    for p in models_path:
        m = importlib.import_module(p)
        for _, obj in inspect.getmembers(m, inspect.isclass):
            if issubclass(obj, DBModel) and obj is not DBModel:
                meta = getattr(obj, "Meta", None)
                if meta and getattr(meta, "table", None) == table_name:
                    field_info = []
                    for field_name, field_obj in obj._meta.fields_map.items():
                        info = {
                            "name": field_name,
                            "type": type(field_obj).__name__,
                            "max_length": getattr(field_obj, "max_length", -1),
                            "nullable": field_obj.null,
                        }
                        field_info.append(info)
                    return field_info
    return []


async def init_db(
    load_module_db: bool = True,
    db_models: list[str] | None = None,
    generate_schemas: bool = False,
) -> bool:
    context = None
    try:
        database_list = fetch_module_db() if load_module_db else []
        database_list += db_models if db_models else []
        context = await Tortoise.init(
            config={
                "connections": {
                    "default": get_db_link(),
                    "local": prepare_db_link(DB_LINK),
                },
                "apps": {
                    "models": {
                        "models": ["core.database.models"] + database_list,
                        "default_connection": "default",
                    },
                    "local_models": {
                        "models": ["core.database.local"],
                        "default_connection": "local",
                    },
                },
            },
            _enable_global_fallback=True,
        )

        if generate_schemas:
            await Tortoise.generate_schemas(safe=True)

        Temp.data["modules_db_list"] = database_list
        return True
    except asyncio.CancelledError:
        # 初始化可能在部分连接建立后被取消。清理完成后保留取消语义，
        # 让上层生命周期控制能够正常停止。
        try:
            await asyncio.shield(Tortoise.close_connections())
        except Exception:
            Logger.exception("Failed to clean up cancelled database initialization.")
        raise
    except Exception:
        Logger.exception()
        # Tortoise.init() 可能在部分连接已经建立后才失败。若把半初始化的
        # 全局状态留给调用方，随后重试会复用或覆盖一套不完整的连接注册表。
        # init_db() 对外以 False 表示失败，因此也应在返回前完成自身回滚。
        try:
            await Tortoise.close_connections()
        except Exception:
            Logger.exception("Failed to clean up partial database initialization.")
        return False
    finally:
        # Tortoise.init() 在无当前 context 时会把初始化 context 写入当前任务。
        # 这会复制给 Queue poller 等后续任务，reload 替换全局 context 后它们
        # 仍会持有旧对象。初始化完成后恢复为“仅使用 global fallback”。
        if isinstance(context, TortoiseContext):
            context.__exit__(None, None, None)


def _database_config(load_module_db: bool, db_models: list[str] | None) -> tuple[dict, list[str]]:
    database_list = fetch_module_db() if load_module_db else []
    database_list += db_models if db_models else []
    return (
        {
            "connections": {
                "default": get_db_link(),
                "local": prepare_db_link(DB_LINK),
            },
            "apps": {
                "models": {
                    "models": ["core.database.models"] + database_list,
                    "default_connection": "default",
                },
                "local_models": {
                    "models": ["core.database.local"],
                    "default_connection": "local",
                },
            },
        },
        database_list,
    )


async def prepare_db_reload(db_models: list[str] | None = None) -> PreparedDatabaseReload | None:
    """Build a replacement context while the old one remains active."""
    from tortoise import context as tortoise_context

    previous_context = tortoise_context.get_current_context()
    config, database_list = _database_config(True, db_models)
    context = TortoiseContext()
    token = tortoise_context._current_context.set(context)
    try:
        await context.init(config=config, _enable_global_fallback=False)
    except asyncio.CancelledError:
        try:
            await asyncio.shield(context.close_connections())
        except Exception:
            Logger.exception("Failed to clean up cancelled database reload preparation.")
        raise
    except Exception:
        Logger.exception()
        try:
            await context.close_connections()
        except Exception:
            Logger.exception("Failed to clean up failed database reload preparation.")
        return None
    finally:
        tortoise_context._current_context.reset(token)
    return PreparedDatabaseReload(context, previous_context, database_list)


def activate_db_reload(prepared: PreparedDatabaseReload) -> None:
    """Atomically publish a prepared context to all tasks using the global fallback."""
    if prepared.activated:
        return
    from tortoise import context as tortoise_context

    # Tortoise 只提供 set_global_context，但缺少可替换现有 global 的公共 API。
    # 在切换前新 context 已完全初始化，故这里是有意的原子替换点。
    tortoise_context._global_context = prepared.context
    if tortoise_context._current_context.get() is prepared.previous_context:
        # 不把新 context 固定到当前任务，否则后续子任务会继续继承任务级对象，
        # 下一次 reload 替换全局 context 时重现旧 context 泄漏。
        tortoise_context._current_context.set(None)
    Temp.data["modules_db_list"] = list(prepared.database_list)
    prepared.activated = True


async def close_prepared_db_reload(prepared: PreparedDatabaseReload) -> None:
    """Discard a prepared context that was not activated."""
    if prepared.activated:
        return
    try:
        await prepared.context.close_connections()
    except Exception:
        Logger.exception("Failed to close an unused prepared database context.")


async def close_previous_db_context(prepared: PreparedDatabaseReload) -> None:
    """Close the context replaced by an activated database reload."""
    if not prepared.activated or prepared.previous_context is None:
        return
    if prepared.previous_context is prepared.context:
        return
    try:
        await prepared.previous_context.close_connections()
    except Exception:
        Logger.exception("Failed to close the previous database context after reload.")


async def reload_db(db_models: list[str] | None = None):
    async with _reload_lock:
        from core.queue.server import JobQueueServer
        from core.scheduler import SchedulerLifecycle

        # 先排空 Queue handler，再停止新 Job 并取消运行中的 Job；新 context
        # 的构建不触碰旧连接，激活与旧 context 关闭在准备完成后完成。
        async with JobQueueServer.maintenance_window(exclusive=True), SchedulerLifecycle.maintenance_window():
            prepared = await prepare_db_reload(db_models)
            if prepared is None:
                return False
            activate_db_reload(prepared)
            close_task = asyncio.create_task(
                close_previous_db_context(prepared),
                name="database-reload-close-previous",
            )
            try:
                await asyncio.shield(close_task)
            except asyncio.CancelledError:
                await close_task
                raise
            return True


async def close_db():
    try:
        await Tortoise.close_connections()
    except Exception:
        pass
    finally:
        # close_connections 只关闭连接，不会移除 Tortoise 的 global fallback。
        # 清理任务级与全局 context，允许后续 init_db() 真正重新初始化。
        from tortoise import context as tortoise_context

        tortoise_context._global_context = None
        tortoise_context._current_context.set(None)
