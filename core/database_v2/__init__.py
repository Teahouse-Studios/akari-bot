from tortoise import Tortoise
from .link import get_db_link

models = ['core.database_v2.models','modules.cytoid.models']

async def init_db():
    await Tortoise.init(
        db_url=get_db_link("tortoise"),
        modules={'models': models, },
    )

    await Tortoise.generate_schemas()
