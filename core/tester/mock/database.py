from tortoise import Tortoise

from core.database import fetch_module_db, close_db
from core.logger import Logger


async def init_db(load_module_db: bool = True) -> bool:
    try:
        database_list = fetch_module_db() if load_module_db else []
        await Tortoise.init(
            config={
                "connections": {
                    "default": "sqlite://:memory:",
                    "local": "sqlite://:memory:",
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
        return True
    except Exception:
        Logger.exception()
        return False

__all__ = ["init_db", "close_db"]
