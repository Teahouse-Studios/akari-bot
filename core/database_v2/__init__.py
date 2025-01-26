from core.config import Config
from core.constants import db_path_default
from tortoise import Tortoise

from .link import get_db_link

db_link = Config("db_path", default=db_path_default, secret=True)


async def init_db():
    await Tortoise.init(
        db_url=get_db_link("tortoise"),
        modules={'models': [
            'core.database_v2.models',
            'modules.cytoid.models',
            'modules.maimai.models',
            'modules.osu.models',
            'modules.phigros.models']
        },
    )

    await Tortoise.generate_schemas()
