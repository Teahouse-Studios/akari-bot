import asyncio
import importlib.util
import inspect
import pkgutil
from typing import Any, Dict, List, Optional

from tortoise import Tortoise
from tortoise.exceptions import DBConnectionError

from core.builtins.temp import Temp
from core.logger import Logger
from .link import get_db_link
from .local import DB_LINK
from .models import DBModel

_reload_lock = asyncio.Lock()


def fetch_module_db():
    import modules
    database_list = []
    for m in pkgutil.iter_modules(modules.__path__):
        try:
            database_list.append(importlib.util.find_spec(f"modules.{m.name}.database.models").name)
        except Exception:
            pass

    Logger.debug(f"Database list: {database_list}")
    return database_list


def get_model_names(models_path: List[str]) -> List[str]:
    table_names = []
    for p in models_path:
        m = importlib.import_module(p)
        for _, obj in inspect.getmembers(m, inspect.isclass):
            if issubclass(obj, DBModel) and obj is not DBModel:
                meta = getattr(obj, "Meta", None)
                if meta and hasattr(meta, "table"):
                    table_names.append(meta.table)

    return table_names


def get_model_fields(models_path: List[str], table_name: str) -> List[Dict[str, Any]]:
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
                            "nullable": field_obj.null
                        }
                        field_info.append(info)
                    return field_info
    return []


async def init_db(load_module_db: bool = True, db_models: Optional[List[str]] = None) -> bool:
    try:
        database_list = fetch_module_db() if load_module_db else []
        database_list += db_models if db_models else []
        await Tortoise.init(
            config={
                "connections": {
                    "default": get_db_link(),
                    "local": DB_LINK,
                },
                "apps": {
                    "models": {
                        "models": ["core.database.models"] + database_list,
                        "default_connection": "default",
                    },
                    "local_models": {
                        "models": ["core.database.local"],
                        "default_connection": "local",
                    }
                }
            }
        )

        await Tortoise.generate_schemas(safe=True)

        Temp.data["modules_db_list"] = database_list
        return True
    except Exception:
        Logger.exception()
        return False


async def reload_db(db_models: Optional[List[str]] = None):
    async with _reload_lock:
        from core.queue.server import JobQueueServer  # noqa

        JobQueueServer.pause_event.clear()
        old_modules_db_list = Temp.data.get("modules_db_list", [])
        try:
            success = await init_db(db_models=db_models)
            if success:
                await Tortoise.close_connections()
                return True
        except DBConnectionError:
            Logger.error("Failed to reload database, fallbacking...")
            return await init_db(load_module_db=False, db_models=old_modules_db_list)
        finally:
            JobQueueServer.pause_event.set()
