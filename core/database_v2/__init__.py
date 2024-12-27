from tortoise import Tortoise
from .link import get_db_link


async def init_db():
    await Tortoise.init(
        db_url=get_db_link("tortoise"),
        modules={'models': ['core.database_v2.models'],},
    )


    await Tortoise.generate_schemas()
