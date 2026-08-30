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


@func_case
async def test_database_update(tester: Tester):
    await tester.test(_test_wiki_url_rules_are_migrated_idempotently, "Wiki URL 规则幂等迁入全局名单")
    await tester.test(_test_invalid_rule_preserves_source_table, "URL 规则迁移失败时保留旧表")
    return tester
