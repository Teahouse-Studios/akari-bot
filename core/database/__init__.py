import os

import orjson as json
from tortoise import Tortoise

from core.config import Config
from core.constants import Info, modules_path
from core.logger import Logger
from core.utils.loader import fetch_modules_list
from .link import get_db_link
from .local import DB_LINK


def fetch_module_db():
    unloaded_modules = Config("unloaded_modules", [])
    Logger.info("Initializing database...")
    dir_list = []
    database_list = []
    if Info.binary_mode:
        try:
            Logger.warning(
                "Binary mode detected, trying to load pre-built modules list..."
            )
            js = "assets/database_list.json"
            with open(js, "r", encoding="utf-8") as f:
                database_list = json.loads(f.read())
        except Exception:
            Logger.error("Failed to load pre-built modules list, using default list.")
            dir_list = os.listdir(modules_path)
    else:
        dir_list = fetch_modules_list()
    if dir_list:
        for file_name in dir_list:
            if os.path.isdir(os.path.join(modules_path, file_name)):
                if os.path.exists(
                    os.path.join(modules_path, file_name, "database/models.py")
                ):
                    if file_name not in unloaded_modules:
                        Logger.debug(f"Found {file_name} database models...")
                        database_list.append(f"modules.{file_name}.database.models")

    Logger.debug(f"Database list: {database_list}")
    return database_list


async def init_db():
    database_list = fetch_module_db()
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

    Logger.success("Database initialized successfully.")
