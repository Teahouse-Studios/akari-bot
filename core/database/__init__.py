import asyncio
import importlib.util
import inspect
import pkgutil
import traceback
from typing import Any

from tortoise import Tortoise

from core.builtins.temp import Temp
from core.logger import Logger
from .link import get_db_link, prepare_db_link
from .local import DB_LINK
from .models import DBModel

_reload_lock = asyncio.Lock()


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
    try:
        database_list = fetch_module_db() if load_module_db else []
        database_list += db_models if db_models else []
        await Tortoise.init(
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


async def reload_db(db_models: list[str] | None = None):
    async with _reload_lock:
        from core.queue.server import JobQueueServer
        from core.scheduler import SchedulerLifecycle

        old_modules_db_list = Temp.data.get("modules_db_list", [])
        # Scheduler 在 Queue 体系之外，同样会读写 Tortoise。必须先停止新 Job、
        # 取消并等待运行中 Job，再排空 Queue handler，最后才能替换全局连接。
        # Loader 已在更外层覆盖 Python reload；该窗口支持同一 Task 重入。
        async with SchedulerLifecycle.maintenance_window(), JobQueueServer.maintenance_window():

            async def restore_previous_models():
                # 失败的初始化可能留下部分连接状态，恢复旧模型前再清理一次。
                await Tortoise.close_connections()
                recovered = await init_db(load_module_db=False, db_models=old_modules_db_list)
                if not recovered:
                    Logger.error("Failed to restore the previous database model list after reload failure.")

            try:
                # Tortoise.init() 会建立一套新连接。旧实现反而在初始化成功后调用 close_connections()，
                # 等于把刚建立的连接立即丢弃；这里先关闭旧连接，再初始化并保留新连接。
                await Tortoise.close_connections()
                success = await init_db(db_models=db_models)
                if success:
                    return True

                # init_db() 统一把底层连接异常转换为 False，故回退不能依赖不可达的异常分支。
                Logger.error("Failed to reload database, falling back to the previous model list...")
                await restore_previous_models()
            except asyncio.CancelledError:
                # 关闭旧连接后若在新连接初始化期间被取消，Server 会继续运行却没有
                # 可用数据库。恢复旧模型后再传播取消，让 Loader 同步回滚注册表。
                try:
                    await asyncio.shield(restore_previous_models())
                except Exception:
                    Logger.exception("Failed to restore database after cancelled reload.")
                raise

            # 回退只保证旧连接可继续使用，不代表调用方请求的新模型已经生效。
            # Loader 必须据此回滚刚注册的模块，故无论恢复是否成功都报告失败。
            return False


async def close_db():
    try:
        await Tortoise.close_connections()
    except Exception:
        pass
