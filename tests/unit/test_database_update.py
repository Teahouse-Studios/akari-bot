"""数据库版本升级测试。"""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, patch

import core.database.update as database_update
from core.tester import Tester, func_case
from core.utils.url_audit import GlobalURLAllowlist, GlobalURLBlocklist, URLRuleError


def _patch_rule_paths(root: Path):
    allowlist_directory = root / "allowlist"
    blocklist_directory = root / "blocklist"
    return (
        patch.object(GlobalURLAllowlist, "directory", allowlist_directory),
        patch.object(GlobalURLAllowlist, "builtin_path", allowlist_directory / "global.txt"),
        patch.object(GlobalURLAllowlist, "user_path", allowlist_directory / "user.txt"),
        patch.object(GlobalURLBlocklist, "directory", blocklist_directory),
        patch.object(GlobalURLBlocklist, "builtin_path", blocklist_directory / "global.txt"),
        patch.object(GlobalURLBlocklist, "user_path", blocklist_directory / "user.txt"),
    )


async def _test_wiki_url_rules_are_migrated_idempotently():
    rows = {
        "module_wiki_allow_list": [
            {"api_link": "https://allowed.example/api.php"},
            {"api_link": r"regex:https://[a-z]{2}\.allowed\.example/w/api\.php"},
        ],
        "module_wiki_block_list": [
            {"api_link": "https://blocked.example/api.php"},
            {"api_link": r"regex:https://[a-z]{2}\.blocked\.example/w/api\.php"},
        ],
    }
    conn = AsyncMock()

    async def execute_query_dict(query, *args):
        for table, records in rows.items():
            if table in query:
                return records
        return []

    conn.execute_query_dict.side_effect = execute_query_dict

    with TemporaryDirectory() as temp_dir:
        path_patches = _patch_rule_paths(Path(temp_dir))
        with path_patches[0], path_patches[1], path_patches[2], path_patches[3], path_patches[4], path_patches[5]:
            GlobalURLAllowlist.clear_cache()
            GlobalURLBlocklist.clear_cache()
            with patch.object(database_update, "has_table", new=AsyncMock(return_value=True)):
                await database_update.update_database_to_v4(conn)
                await database_update.update_database_to_v4(conn)

            allowlist_lines = GlobalURLAllowlist.user_path.read_text(encoding="utf-8").splitlines()
            blocklist_lines = GlobalURLBlocklist.user_path.read_text(encoding="utf-8").splitlines()
            result = (
                allowlist_lines == [record["api_link"] for record in rows["module_wiki_allow_list"]]
                and blocklist_lines == [record["api_link"] for record in rows["module_wiki_block_list"]]
                and GlobalURLAllowlist.is_allowed("https://allowed.example/api.php")
                and GlobalURLAllowlist.is_allowed("https://zh.allowed.example/w/api.php")
                and GlobalURLBlocklist.is_blocked("https://blocked.example/api.php")
                and GlobalURLBlocklist.is_blocked("https://en.blocked.example/w/api.php")
                and conn.execute_query.await_count == 4
            )
            GlobalURLAllowlist.clear_cache()
            GlobalURLBlocklist.clear_cache()
            return result


async def _test_invalid_rule_preserves_source_table():
    conn = AsyncMock()
    conn.execute_query_dict.return_value = [{"api_link": "regex:.*"}]

    with TemporaryDirectory() as temp_dir:
        path_patches = _patch_rule_paths(Path(temp_dir))
        with path_patches[0], path_patches[1], path_patches[2], path_patches[3], path_patches[4], path_patches[5]:
            GlobalURLAllowlist.clear_cache()
            with patch.object(database_update, "has_table", new=AsyncMock(return_value=True)):
                try:
                    await database_update.update_database_to_v4(conn)
                except URLRuleError as exc:
                    result = exc.reason == "broad_regex" and conn.execute_query.await_count == 0
                else:
                    result = False
            GlobalURLAllowlist.clear_cache()
            return result


async def _test_jobqueue_v5_migration_drops_and_recreates_table():
    for db_type, drop_statement in (
        ("sqlite", 'DROP TABLE IF EXISTS "job_queues";'),
        ("mysql", "DROP TABLE IF EXISTS `job_queues`;"),
    ):
        conn = AsyncMock()
        generate_schemas = AsyncMock()

        with (
            patch.object(database_update, "db_type", db_type),
            patch.object(database_update.Tortoise, "generate_schemas", new=generate_schemas),
        ):
            await database_update.update_database_to_v5(conn)

        if not (
            conn.execute_query.await_count == 1
            and conn.execute_query.await_args.args == (drop_statement,)
            and generate_schemas.await_count == 1
            and generate_schemas.await_args.kwargs == {"safe": True}
        ):
            return False
    return True


async def _test_jobqueue_v5_migration_recreates_current_sqlite_schema():
    conn = database_update.Tortoise.get_connection("default")
    await conn.execute_query('DROP TABLE IF EXISTS "job_queues";')
    await conn.execute_query("""
        CREATE TABLE "job_queues" (
            "task_id" CHAR(36) PRIMARY KEY,
            "target_client" VARCHAR(512) NOT NULL,
            "action" VARCHAR(512) NOT NULL,
            "args" JSON NOT NULL DEFAULT '{}',
            "status" VARCHAR(32) NOT NULL DEFAULT 'pending',
            "result" JSON NOT NULL DEFAULT '{}',
            "timestamp" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
    """)
    await conn.execute_query("""
        INSERT INTO "job_queues" ("task_id", "target_client", "action")
        VALUES ('00000000-0000-0000-0000-000000000001', 'client:test', 'legacy.action');
    """)

    try:
        with patch.object(database_update, "db_type", "sqlite"):
            await database_update.update_database_to_v5(conn)

        columns = {row["name"] for row in await conn.execute_query_dict('PRAGMA table_info("job_queues");')}
        rows = await conn.execute_query_dict('SELECT * FROM "job_queues";')
        return (
            not rows
            and "target_client" not in columns
            and {
                "task_id",
                "correlation_id",
                "source_peer_id",
                "target_peer",
                "message_kind",
                "action",
                "args",
                "status",
                "claimed_by",
                "result",
                "timestamp",
            }
            <= columns
        )
    finally:
        await conn.execute_query('DROP TABLE IF EXISTS "job_queues";')
        await database_update.Tortoise.generate_schemas(safe=True)


@func_case
async def test_database_update(tester: Tester):
    await tester.test(_test_wiki_url_rules_are_migrated_idempotently, "Wiki URL 规则幂等迁入全局名单")
    await tester.test(_test_invalid_rule_preserves_source_table, "URL 规则迁移失败时保留旧表")
    await tester.test(
        _test_jobqueue_v5_migration_drops_and_recreates_table,
        "JobQueue v5 删除旧任务表并触发安全建表",
    )
    await tester.test(
        _test_jobqueue_v5_migration_recreates_current_sqlite_schema,
        "JobQueue v5 丢弃旧任务并重建当前 SQLite 表结构",
    )
    return tester
