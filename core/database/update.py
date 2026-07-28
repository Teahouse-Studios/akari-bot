from tortoise import Tortoise

from core.database import fetch_module_db
from core.database.link import db_type, get_db_link
from core.database.models import DBVersion, TargetInfo, TargetUnionBind, backfill_union_binds

# v3：原本以平台 ID 为主键的表改挂 union，旧数据的 union ID 直接沿用原 ID，因此只需重命名主键列。
UNION_RENAME_TABLES = {
    "sender_id": [
        "sender_info",
        "module_cytoid_bind_info",
        "module_maimai_diving_prober_bind_info",
        "module_maimai_lxns_prober_bind_info",
        "module_phigros_bind_info",
    ],
    "target_id": [
        "target_info",
        "module_wiki_target_set_info",
        "module_wikilog_target_set_info",
    ],
}

# v3：统计与审计表保留原始 ID，另增 union 列用于聚合。
UNION_RECORD_TABLES = ["analytics_data", "unfriendly_actions"]


async def has_column(conn, table: str, column: str) -> bool:
    """
    判断某张表中是否存在指定列，表不存在时同样返回 False。

    :param conn: 数据库连接。
    :param table: 表名。
    :param column: 列名。
    """
    if db_type == "sqlite":
        rows = await conn.execute_query_dict(f'PRAGMA table_info("{table}");')
        return any(row["name"] == column for row in rows)
    rows = await conn.execute_query_dict(
        "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = %s;",
        [table, column],
    )
    return bool(rows)


async def update_database_to_v3(conn):
    """
    将数据库升级至 v3：平台 ID 与数据解耦，数据改挂 union。

    :param conn: 数据库连接。
    """
    # 主键列改名。表由 generate_schemas() 新建时已是 union_id，此时旧列不存在，跳过即可。
    for old_column, tables in UNION_RENAME_TABLES.items():
        for table in tables:
            if not await has_column(conn, table, old_column):
                continue
            if db_type == "sqlite":
                await conn.execute_query(f'ALTER TABLE "{table}" RENAME COLUMN "{old_column}" TO "union_id";')
            else:
                # CHANGE COLUMN 兼容 MySQL 8.0 以下版本。
                await conn.execute_query(
                    f"ALTER TABLE `{table}` CHANGE COLUMN `{old_column}` `union_id` VARCHAR(512) NOT NULL;"
                )

    # 补建映射行。旧数据的 union ID 与原 ID 相同，直接按原值一一对应即可。
    # 账号级封禁保持关闭，原有的封禁状态已记在 union 上。
    await backfill_union_binds()

    # 消息通道号。target_union_bind 由 generate_schemas() 新建时已包含该列，正常升级路径不会执行此段；
    # 保留该段是为了让开发期已升级至 v3、其后才引入通道功能的数据库可将版本号退回 2 重跑一次修复。
    if not await has_column(conn, "target_union_bind", "channel_id"):
        if db_type == "sqlite":
            await conn.execute_query('ALTER TABLE "target_union_bind" ADD COLUMN "channel_id" INT NOT NULL DEFAULT 1;')
        else:
            await conn.execute_query("ALTER TABLE `target_union_bind` ADD COLUMN `channel_id` INT NOT NULL DEFAULT 1;")

    # 通道号须在组内逐个顺延。若一律保留默认值 1，同一组下的全部会话会被判定为同一条消息通道，
    # 命令与推送将相互去重，导致会话不再有消息送达。
    for union_id in set(await TargetUnionBind.all().values_list("union_id", flat=True)):
        binds = await TargetUnionBind.filter(union_id=union_id).order_by("bound_at")
        for channel_id, bind in enumerate(binds, start=1):
            bind.channel_id = channel_id
            await bind.save()

    # 旧版 connect 将机器人互认记录存为扁平列表，无法反查某条记录属于哪个会话，解绑时也就无从删除。
    # 该结构已改为两级字典，旧值直接清除，重新执行一次 bind auto 即可。
    for target in await TargetInfo.all():
        if isinstance(target.target_data.get("bots_id"), list):
            target.target_data.pop("bots_id")
            await target.save()

    # 统计与审计表增列并回填，历史记录的原始 ID 保持不动。
    for table in UNION_RECORD_TABLES:
        for column, source in (("target_union_id", "target_id"), ("sender_union_id", "sender_id")):
            if await has_column(conn, table, column):
                continue
            if db_type == "sqlite":
                await conn.execute_query(f'ALTER TABLE "{table}" ADD COLUMN "{column}" VARCHAR(512) NULL;')
            else:
                await conn.execute_query(f"ALTER TABLE `{table}` ADD COLUMN `{column}` VARCHAR(512) NULL;")
            await conn.execute_query(f"UPDATE {table} SET {column} = {source} WHERE {column} IS NULL;")


async def update_database():
    database_list = fetch_module_db()
    await Tortoise.init(db_url=get_db_link(), modules={"models": ["core.database.models"] + database_list})

    await Tortoise.generate_schemas(safe=True)

    conn = Tortoise.get_connection("default")
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
                                         ALTER TABLE target_info
                                             ADD COLUMN banned_users JSON DEFAULT NULL AFTER custom_admins;

                                         UPDATE target_info
                                         SET banned_users =
                                                 IF(
                                                     JSON_CONTAINS_PATH(target_data, 'one', '$.ban'),
                                                     JSON_EXTRACT(target_data, '$.ban'),
                                                     JSON_ARRAY()
                                                 ),
                                             target_data  = JSON_REMOVE(target_data, '$.ban');

                                         ALTER TABLE analytics_data
                                             MODIFY sender_id VARCHAR(512) NULL;

                                         """)

            await query_dbver.delete()
            await DBVersion.create(version=2)
        if db_version < 3:
            query_dbver = await DBVersion.first()

            await update_database_to_v3(conn)

            await query_dbver.delete()
            await DBVersion.create(version=3)

    await Tortoise.close_connections()
