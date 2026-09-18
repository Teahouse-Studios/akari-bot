import traceback

from tortoise import Tortoise
from tortoise.context import TortoiseContext

from core.database import fetch_module_db, close_db
from core.logger import Logger

_last_init_error = ""


def get_last_init_error() -> str:
    """返回最近一次测试数据库初始化失败的诊断信息。"""
    return _last_init_error


async def init_db(load_module_db: bool = True) -> bool:
    global _last_init_error

    context = None
    stage = "discovering module database models"
    try:
        database_list = fetch_module_db() if load_module_db else []
        stage = "initializing Tortoise ORM"
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

        stage = "generating SQLite schemas"
        await Tortoise.generate_schemas(safe=True)
        _last_init_error = ""
        return True
    except Exception:
        _last_init_error = f"Test database initialization failed while {stage}:\n{traceback.format_exc()}"
        Logger.exception()
        return False
    finally:
        if isinstance(context, TortoiseContext):
            context.__exit__(None, None, None)


__all__ = ["init_db", "get_last_init_error", "close_db"]
