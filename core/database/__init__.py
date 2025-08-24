import importlib.util
import pkgutil
from typing import List, Optional

from tortoise import Tortoise

from core.builtins.temp import Temp
from core.config import CFGManager
from core.logger import Logger
from .link import get_db_link
from .local import DB_LINK


def fetch_module_db():
    import modules
    unloaded_modules = CFGManager.get("unloaded_modules", [])
    database_list = []
    for m in pkgutil.iter_modules(modules.__path__):
        try:
            if m.name not in unloaded_modules:
                database_list.append(importlib.util.find_spec(f"modules.{m.name}.database.models").name)
        except ModuleNotFoundError:
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
    await Tortoise.close_connections()
    if not await init_db(db_models=db_models):
        Logger.error("Failed to reload database, fallbacking...")
        return await init_db(load_module_db=False, db_models=Temp.data["modules_db_list"])
    return True
