from tortoise import Tortoise, connections

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
            conn = connections.get("default")
            await conn.execute_query("ALTER TABLE analytics_data MODIFY sender_id VARCHAR(512) NULL;")
            
            await query_dbver.delete()
            await DBVersion.create(version=2)
        if db_version < 3:
            conn = connections.get("default")
            ...
            await query_dbver.delete()
            await DBVersion.create(version=3)
    await Tortoise.close_connections()
