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

                    CREATE TABLE _new_target_info (
                        target_id VARCHAR(512) PRIMARY KEY,
                        blocked BOOLEAN NOT NULL,
                        muted BOOLEAN NOT NULL,
                        locale VARCHAR(32) NOT NULL,
                        modules JSON NOT NULL DEFAULT '[]',
                        custom_admins JSON NOT NULL DEFAULT '[]',
                        banned_users JSON NOT NULL DEFAULT '[]',
                        target_data JSON NOT NULL DEFAULT '{}'
                    );

                    INSERT INTO _new_target_info (target_id, blocked, muted, locale, modules, custom_admins, banned_users, target_data)
                    SELECT target_id, blocked, muted, locale, modules, custom_admins, '[]', target_data FROM target_info;

                    DROP TABLE target_info;
                    ALTER TABLE _new_target_info RENAME TO target_info;

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
                await conn.execute_query("""
                    ALTER TABLE target_info ADD COLUMN banned_users JSON DEFAULT NULL AFTER custom_admins;

                    UPDATE target_info
                    SET banned_users =
                        IF(
                            JSON_CONTAINS_PATH(target_data, 'one', '$.ban'),
                            JSON_EXTRACT(target_data, '$.ban'),
                            JSON_ARRAY()
                        ),
                        target_data = JSON_REMOVE(target_data, '$.ban');

                    ALTER TABLE analytics_data MODIFY sender_id VARCHAR(512) NULL;

                """)

            await query_dbver.delete()
            await DBVersion.create(version=2)
        if db_version < 3:
            # query_dbver = await DBVersion.first()
            ...
            # await query_dbver.delete()
            # await DBVersion.create(version=3)

    await Tortoise.close_connections()
