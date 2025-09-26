import asyncio
import importlib.util
import pkgutil
from typing import List, Optional

from tortoise import Tortoise
from tortoise.exceptions import DBConnectionError

from core.builtins.temp import Temp
from core.logger import Logger
from .link import get_db_link
from .local import DB_LINK

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
