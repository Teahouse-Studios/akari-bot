from tortoise import Tortoise

from core.database import fetch_module_db
from core.database.link import get_db_link
from core.database.models import DBVersion

database_list = fetch_module_db()


async def update_database():
    await Tortoise.init(
        db_url=get_db_link(),
        modules={"models": ["core.database.models"] + database_list}
    )

    await Tortoise.generate_schemas(safe=True)

    query_dbver = await DBVersion.first()
    if query_dbver:
        db_version = query_dbver.version
        if db_version < 2:
            ...
            await query_dbver.delete()
        await DBVersion.create(version=2)
    await Tortoise.close_connections()
