from tortoise import Tortoise, connections

from core.database import fetch_module_db
from core.database.link import db_type, get_db_link
from core.database.models import DBVersion

database_list = fetch_module_db()


async def update_database():
    await Tortoise.init(
        db_url=get_db_link(),
        modules={"models": ["core.database.models"] + database_list}
    )

    await Tortoise.generate_schemas(safe=True)

    conn = connections.get("default")
    query_dbver = await DBVersion.first()
    if query_dbver:
        db_version = query_dbver.version
        if db_version < 2:
            query_dbver = await DBVersion.first()

            if db_type == "sqlite":
                await conn.execute_script("""
                    PRAGMA foreign_keys=off;

                    CREATE TABLE _new_analytics_data (
                        id INTEGER PRIMARY KEY,
                        module_name VARCHAR(512) NOT NULL,
                        module_type VARCHAR(512) NOT NULL,
                        target_id VARCHAR(512) NOT NULL,
                        sender_id VARCHAR(512),
                        command TEXT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                    );

                    INSERT INTO _new_analytics_data (id, module_name, module_type, target_id, sender_id, command, timestamp)
                    SELECT id, module_name, module_type, target_id, sender_id, command, timestamp FROM analytics_data;

                    DROP TABLE analytics_data;
                    ALTER TABLE _new_analytics_data RENAME TO analytics_data;

                    PRAGMA foreign_keys=on;
                """)
            else:
                await conn.execute_query("ALTER TABLE analytics_data MODIFY sender_id VARCHAR(512) NULL;")

            await query_dbver.delete()
            await DBVersion.create(version=2)
        if db_version < 3:
            # query_dbver = await DBVersion.first()
            ...
            # await query_dbver.delete()
            # await DBVersion.create(version=3)

    await Tortoise.close_connections()
