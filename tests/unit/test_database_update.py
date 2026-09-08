"""URL 全局规则的数据库升级测试。"""

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


async def _test_jobqueue_v5_migration_adds_complete_peer_delivery_schema():
    for db_type in ("sqlite", "mysql"):
        conn = AsyncMock()

        async def has_old_column(_conn, _table, column):
            return column == "target_client"

        with (
            patch.object(database_update, "db_type", db_type),
            patch.object(database_update, "has_column", new=has_old_column),
            patch.object(database_update, "has_index", new=AsyncMock(return_value=False)),
        ):
            await database_update.update_database_to_v5(conn)
        queries = "\n".join(call.args[0] for call in conn.execute_query.await_args_list)
        if not all(field in queries for field in ("correlation_id", "source_peer_id", "message_kind", "claimed_by")):
            return False
        rename_syntax = "RENAME COLUMN" if db_type == "sqlite" else " CHANGE "
        if rename_syntax not in queries or "target_peer" not in queries or "target_client" not in queries:
            return False

    existing = AsyncMock()

    async def has_current_column(_conn, _table, column):
        return column != "target_client"

    with (
        patch.object(database_update, "has_column", new=has_current_column),
        patch.object(database_update, "has_index", new=AsyncMock(return_value=True)),
    ):
        await database_update.update_database_to_v5(existing)
    if existing.execute_query.await_count:
        return False

    partial = AsyncMock()
    partial.execute_query_dict.side_effect = [
        [{"name": "idx_job_queues_client_status"}],
        [{"name": "target_client"}, {"name": "status"}],
    ]

    async def has_partial_column(_conn, _table, _column):
        return True

    with (
        patch.object(database_update, "db_type", "sqlite"),
        patch.object(database_update, "has_column", new=has_partial_column),
        patch.object(database_update, "has_index", new=AsyncMock(return_value=False)),
    ):
        await database_update.update_database_to_v5(partial)
    partial_queries = "\n".join(call.args[0] for call in partial.execute_query.await_args_list)
    if not all(statement in partial_queries for statement in ("UPDATE", "DROP INDEX", "DROP COLUMN", "CREATE INDEX")):
        return False

    partial_mysql = AsyncMock()
    partial_mysql.execute_query_dict.return_value = [{"INDEX_NAME": "idx_job_queues_client_status"}]
    with (
        patch.object(database_update, "db_type", "mysql"),
        patch.object(database_update, "has_column", new=has_partial_column),
        patch.object(database_update, "has_index", new=AsyncMock(return_value=False)),
    ):
        await database_update.update_database_to_v5(partial_mysql)
    mysql_queries = "\n".join(call.args[0] for call in partial_mysql.execute_query.await_args_list)
    if not all(
        statement in mysql_queries
        for statement in ("UPDATE", "DROP INDEX", "DROP COLUMN", "CREATE INDEX")
    ):
        return False
    return True


@func_case
async def test_database_update(tester: Tester):
    await tester.test(_test_wiki_url_rules_are_migrated_idempotently, "Wiki URL 规则幂等迁入全局名单")
    await tester.test(_test_invalid_rule_preserves_source_table, "URL 规则迁移失败时保留旧表")
    await tester.test(
        _test_jobqueue_v5_migration_adds_complete_peer_delivery_schema,
        "JobQueue v5 完整实例投递结构迁移",
    )
    return tester
