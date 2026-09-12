from tortoise import Tortoise
from tortoise.context import TortoiseContext

from core.database import fetch_module_db, close_db
from core.logger import Logger


async def init_db(load_module_db: bool = True) -> bool:
    context = None
    try:
        database_list = fetch_module_db() if load_module_db else []
        context = await Tortoise.init(
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
                    },
                },
            },
            _enable_global_fallback=True,
        )

        await Tortoise.generate_schemas(safe=True)
        return True
    except Exception:
        Logger.exception()
        return False
    finally:
        if isinstance(context, TortoiseContext):
            context.__exit__(None, None, None)


__all__ = ["init_db", "close_db"]
