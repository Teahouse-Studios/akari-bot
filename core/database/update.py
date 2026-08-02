from tortoise import Tortoise

from core.database import fetch_module_db
from core.database.link import db_type, get_db_link
from core.database.models import DBVersion, TargetUnionInfo, TargetUnionBind, backfill_union_binds

# v3：原本以平台 ID 为主键的两张核心表改挂 union，表名一并对齐模型名，
# 以免「target_info」这类旧名继续读作「平台场景信息」。
UNION_RENAME_CORE_TABLES = {
    "sender_info": "sender_union_info",
    "target_info": "target_union_info",
}

# v3：原本以平台 ID 为主键的表改挂 union，旧数据的 union ID 直接沿用原 ID，因此只需重命名主键列。
UNION_RENAME_TABLES = {
    "sender_id": [
        "sender_union_info",
        "module_cytoid_bind_info",
        "module_maimai_diving_prober_bind_info",
        "module_maimai_lxns_prober_bind_info",
        "module_phigros_bind_info",
    ],
    "target_id": [
        "target_union_info",
        "module_wiki_target_set_info",
        "module_wikilog_target_set_info",
    ],
}

# v3：统计与审计表保留原始 ID，另增 union 列用于聚合。
UNION_RECORD_TABLES = ["analytics_data", "unfriendly_actions"]


def quote_ident(name: str) -> str:
    """
    按当前数据库类型给标识符加引号。

    :param name: 表名或列名。
    """
    return f'"{name}"' if db_type == "sqlite" else f"`{name}`"


async def has_table(conn, table: str) -> bool:
    """
    判断某张表是否存在。

    :param conn: 数据库连接。
    :param table: 表名。
    """
    if db_type == "sqlite":
        rows = await conn.execute_query_dict(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?;", [table]
        )
    else:
        rows = await conn.execute_query_dict(
            "SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s;",
            [table],
        )
    return bool(rows)


async def has_column(conn, table: str, column: str) -> bool:
    """
    判断某张表中是否存在指定列，表不存在时同样返回 False。

    :param conn: 数据库连接。
    :param table: 表名。
    :param column: 列名。
    """
    if db_type == "sqlite":
        rows = await conn.execute_query_dict(f"PRAGMA table_info({quote_ident(table)});")
        return any(row["name"] == column for row in rows)
    rows = await conn.execute_query_dict(
        "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = %s;",
        [table, column],
    )
    return bool(rows)


async def has_index(conn, table: str, column: str) -> bool:
    """
    判断某张表的指定列上是否已有索引（作为任意索引的首列即算）。

    按列而非按索引名判断：新建的库由 ``generate_schemas`` 依模型声明建索引，索引名由 ORM 生成，
    与迁移里显式指定的名字不同；若按名字判断，已有索引的库会被重复建一份。

    :param conn: 数据库连接。
    :param table: 表名。
    :param column: 列名。
    """
    if db_type == "sqlite":
        indexes = await conn.execute_query_dict(f"PRAGMA index_list({quote_ident(table)});")
        for index in indexes:
            columns = await conn.execute_query_dict(f"PRAGMA index_info({quote_ident(index['name'])});")
            if columns and columns[0]["name"] == column:
                return True
        return False
    rows = await conn.execute_query_dict(
        "SELECT INDEX_NAME FROM information_schema.STATISTICS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = %s AND SEQ_IN_INDEX = 1;",
        [table, column],
    )
    return bool(rows)


async def update_database_to_v3(conn):
    """
    将数据库升级至 v3：平台 ID 与数据解耦，数据改挂 union。

    :param conn: 数据库连接。
    """
    # 核心表改名。update_database() 已先跑过 generate_schemas()，按新模型建出的目标表此刻为空表，
    # 须先移除再改名，否则改名会与之冲突。目标表若已有数据，说明改名早已完成，跳过即可。
    for old_table, new_table in UNION_RENAME_CORE_TABLES.items():
        if not await has_table(conn, old_table):
            continue
        if await has_table(conn, new_table):
            rows = await conn.execute_query_dict(f"SELECT COUNT(*) AS cnt FROM {quote_ident(new_table)};")
            if rows and rows[0]["cnt"]:
                continue
            await conn.execute_query(f"DROP TABLE {quote_ident(new_table)};")
        await conn.execute_query(f"ALTER TABLE {quote_ident(old_table)} RENAME TO {quote_ident(new_table)};")

    # 主键列改名。表由 generate_schemas() 新建时已是 union_id，此时旧列不存在，跳过即可。
    for old_column, tables in UNION_RENAME_TABLES.items():
        for table in tables:
            if not await has_column(conn, table, old_column):
                continue
            if db_type == "sqlite":
                await conn.execute_query(
                    f"ALTER TABLE {quote_ident(table)} RENAME COLUMN {quote_ident(old_column)} TO 'union_id';"
                )
            else:
                # CHANGE COLUMN 兼容 MySQL 8.0 以下版本。
                await conn.execute_query(
                    f"ALTER TABLE {quote_ident(table)} CHANGE COLUMN {quote_ident(old_column)} {quote_ident('union_id')} VARCHAR(512) NOT NULL;"
                )

    # 补建映射行。旧数据的 union ID 与原 ID 相同，直接按原值一一对应即可。
    # 账号级封禁保持关闭，原有的封禁状态已记在 union 上。
    await backfill_union_binds()

    # 消息通道号。target_union_bind 由 generate_schemas() 新建时已包含该列，正常升级路径不会执行此段；
    if not await has_column(conn, "target_union_bind", "channel_id"):
        if db_type == "sqlite":
            await conn.execute_query('ALTER TABLE "target_union_bind" ADD COLUMN "channel_id" INT NOT NULL DEFAULT 1;')
        else:
            await conn.execute_query("ALTER TABLE `target_union_bind` ADD COLUMN `channel_id` INT NOT NULL DEFAULT 1;")

    # 通道号须在组内逐个顺延。若一律保留默认值 1，同一组下的全部场景会被判定为同一条消息通道，
    # 命令与推送将相互去重，导致场景不再有消息送达。
    for union_id in set(await TargetUnionBind.all().values_list("union_id", flat=True)):
        binds = await TargetUnionBind.filter(union_id=union_id).order_by("bound_at")
        for channel_id, bind in enumerate(binds, start=1):
            bind.channel_id = channel_id
            await bind.save()

    # 旧版 connect 将机器人互认记录存为扁平列表，无法反查某条记录属于哪个场景，解绑时也就无从删除。
    # 该结构已改为两级字典，旧值直接清除，重新执行一次 bind auto 即可。
    for target in await TargetUnionInfo.all():
        if isinstance(target.target_data.get("bots_id"), list):
            target.target_data.pop("bots_id")
            await target.save()

    # 统计与审计表增列并回填，历史记录的原始 ID 保持不动。
    for table in UNION_RECORD_TABLES:
        for column, source in (("target_union_id", "target_id"), ("sender_union_id", "sender_id")):
            if await has_column(conn, table, column):
                continue
            if db_type == "sqlite":
                await conn.execute_query(
                    f"ALTER TABLE {quote_ident(table)} ADD COLUMN {quote_ident(column)} VARCHAR(512) NULL;"
                )
            else:
                await conn.execute_query(
                    f"ALTER TABLE {quote_ident(table)} ADD COLUMN {quote_ident(column)} VARCHAR(512) NULL;"
                )
            await conn.execute_query(
                f"UPDATE {quote_ident(table)} SET {quote_ident(column)} = {quote_ident(source)} WHERE {quote_ident(column)} IS NULL;"
            )

    # 轮询与区间统计所需的索引。job_queues 每 100 毫秒被每个进程轮询一次，analytics_data 则要
    # 按时间区间反复聚合，两者都随行数增长退化为全表扫描。表由 generate_schemas() 新建时已依模型
    # 声明建好索引，此处只补既有库；与上面的 channel_id 一样，开发期已升级至 v3 的数据库需将版本号
    # 退回 2 重跑一次方能补上。
    for table, column, index_name in (
        ("job_queues", "target_client", "idx_job_queues_client_status"),
        ("analytics_data", "timestamp", "idx_analytics_data_timestamp"),
    ):
        if await has_index(conn, table, column):
            continue
        if db_type == "sqlite":
            columns = (
                f"{quote_ident('target_client')}, {quote_ident('status')}"
                if table == "job_queues"
                else quote_ident(column)
            )
            await conn.execute_query(f"CREATE INDEX {quote_ident(index_name)} ON {quote_ident(table)} ({columns});")
        else:
            columns = (
                f"{quote_ident('target_client')}, {quote_ident('status')}"
                if table == "job_queues"
                else quote_ident(column)
            )
            await conn.execute_query(f"CREATE INDEX {quote_ident(index_name)} ON {quote_ident(table)} ({columns});")

    if not await has_column(conn, "module_phigros_bind_info", "is_international"):
        if db_type == "sqlite":
            await conn.execute_query(
                f"ALTER TABLE {quote_ident('module_phigros_bind_info')} ADD COLUMN {quote_ident('is_international')} INT NOT NULL DEFAULT 0;"
            )
        else:
            await conn.execute_query(
                f"ALTER TABLE {quote_ident('module_phigros_bind_info')} ADD COLUMN {quote_ident('is_international')} BOOL NOT NULL DEFAULT 0;"
            )


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
