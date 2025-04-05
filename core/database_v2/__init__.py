from tortoise import Tortoise

from .link import get_db_link
from .local import DB_LINK


async def init_db():
    await Tortoise.init(
        config={
            "connections": {
                "default": get_db_link("tortoise"),
                "local": DB_LINK,
            },
            "apps": {
                "models": {
                    "models": ["core.database_v2.models",
                               "modules.cytoid.models",
                               "modules.maimai.models",
                               "modules.osu.models",
                               "modules.phigros.models",
                               "modules.wiki.models"],
                    "default_connection": "default",
                },
                "local_models": {
                    "models": ["core.database_v2.local"],
                    "default_connection": "local",
                }
            }
        }
    )

    await Tortoise.generate_schemas()
