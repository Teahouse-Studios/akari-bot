
from core.config import Config
from core.constants import db_path_default
from tortoise import Tortoise

db_link = Config("db_path", default=db_path_default, secret=True)


async def init_db():
    await Tortoise.init(
        db_url=db_link,
        modules={'models': ['core.database_v2.models'], },
    )

    await Tortoise.generate_schemas()
