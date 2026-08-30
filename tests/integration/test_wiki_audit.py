"""wiki-audit 向全局 URL 允许列表添加规范 Wiki API URL。"""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, patch

from core.tester import Contains, Tester, func_case
from core.utils.url_policy import GlobalURLAllowlist, GlobalURLBlocklist
from modules.wiki.utils.wikilib import BlockedWikiError, WikiInfo, WikiLib, WikiStatus

PAGE_URL = "https://wiki.example.test/wiki/Example_Page"
API_URL = "https://wiki.example.test/w/api.php"


@func_case
async def test_wiki_audit_global_allowlist(tester: Tester):
    resolver = AsyncMock(
        return_value=WikiStatus(
            available=True,
            value=WikiInfo(api=API_URL, name="Example Wiki"),
            message="",
        )
    )
    cache_resolver = AsyncMock(
        return_value=WikiStatus(
            available=True,
            value=WikiInfo(api=API_URL, name="Example Wiki"),
            message="",
        )
    )
    with TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        allowlist_directory = root / "allowlist"
        blocklist_directory = root / "blocklist"
        with (
            patch.object(GlobalURLAllowlist, "directory", allowlist_directory),
            patch.object(GlobalURLAllowlist, "builtin_path", allowlist_directory / "global.txt"),
            patch.object(GlobalURLAllowlist, "user_path", allowlist_directory / "user.txt"),
            patch.object(GlobalURLBlocklist, "directory", blocklist_directory),
            patch.object(GlobalURLBlocklist, "builtin_path", blocklist_directory / "global.txt"),
            patch.object(GlobalURLBlocklist, "user_path", blocklist_directory / "user.txt"),
            patch.object(WikiLib, "check_wiki_available", new=resolver),
            patch.object(WikiLib, "check_wiki_info_from_database_cache", new=cache_resolver),
        ):
            GlobalURLAllowlist.clear_cache()
            GlobalURLBlocklist.clear_cache()
            await tester.integrate(
                f"~wiki-audit trust {PAGE_URL}",
                Contains(f"已将规则加入用户自定义 URL 允许列表：{API_URL}"),
                "wiki-audit 应将页面解析得到的 API URL 加入全局允许列表",
            )
            await tester.test(
                lambda: (
                    GlobalURLAllowlist.is_allowed(API_URL)
                    and not GlobalURLAllowlist.is_allowed(PAGE_URL)
                    and GlobalURLAllowlist.user_path.read_text(encoding="utf-8").splitlines() == [API_URL]
                ),
                "wiki-audit 只应写入规范 API URL",
            )
            await tester.integrate(
                f"~wiki-audit query {PAGE_URL}",
                Contains("已被以下全局规则放行"),
                "query 应查询页面对应 API URL 的全局 allowlist 状态",
            )
            await tester.integrate(
                f"~wau trust {PAGE_URL}",
                Contains(f"规则已存在于全局 URL 允许列表中：{API_URL}"),
                "wiki-audit 别名应保留且重复添加保持幂等",
            )
            await tester.integrate(
                f"~wiki-audit block {PAGE_URL}",
                Contains("已将规则加入用户自定义 URL 阻止列表"),
                "block 应将解析得到的 API URL 加入全局 blocklist",
            )
            await tester.test(
                lambda: (
                    GlobalURLBlocklist.is_blocked(API_URL)
                    and not GlobalURLBlocklist.is_blocked(PAGE_URL)
                    and GlobalURLBlocklist.user_path.read_text(encoding="utf-8").splitlines() == [API_URL]
                ),
                "block 只应写入规范 API URL",
            )
            await tester.integrate(
                f"~wiki-audit distrust {PAGE_URL}",
                Contains("已从用户自定义 URL 允许列表删除规则"),
                "distrust 应使用缓存解析 API URL 并移除 allowlist 规则",
            )
            await tester.integrate(
                f"~wiki-audit unblock {PAGE_URL}",
                Contains("已从用户自定义 URL 阻止列表删除规则"),
                "unblock 应使用缓存解析 API URL 并移除 blocklist 规则",
            )
            await tester.integrate(
                f"~wiki-audit query {PAGE_URL}",
                Contains("未被全局 URL 允许列表放行"),
                "query 应报告未命中 allowlist 的 API URL",
            )
            resolver.return_value = WikiStatus(available=False, value=False, message="not a MediaWiki")
            await tester.integrate(
                "~wiki-audit trust https://invalid.example.test/page",
                Contains("无法添加此 Wiki"),
                "Wiki 地址解析失败时不应写入允许列表",
            )
            resolver.side_effect = BlockedWikiError("https://blocked.example.test/wiki/Page")
            await tester.integrate(
                "~wiki-audit trust https://blocked.example.test/wiki/Page",
                Contains("处于阻止列表中"),
                "wiki-audit 不应绕过全局 URL 阻止列表",
            )
            await tester.test(
                lambda: (
                    GlobalURLAllowlist.user_path.read_text(encoding="utf-8") == ""
                    and GlobalURLBlocklist.user_path.read_text(encoding="utf-8") == ""
                ),
                "Wiki 解析失败或被阻止时不应修改全局名单",
            )
        GlobalURLAllowlist.clear_cache()
        GlobalURLBlocklist.clear_cache()
    return tester
