from core.database.models import DBVersion


async def update_database():
    query_dbver = await DBVersion.first()
    if query_dbver:
        db_version = query_dbver.version
        if db_version < 2:
            ...
            await query_dbver.delete()
        await DBVersion.create(version=2)
