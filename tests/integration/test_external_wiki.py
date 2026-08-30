"""wiki 模块高级集成测试 - search、iw、headers、prefix。

wiki 模块的绝大多数子命令都要求当前场景已设置默认 Wiki，否则一律直接返回提示。
每个 func_case 运行前数据库都会重建，场景状态不会跨用例保留，因此每个用例都需
自行完成设置。相关请求由 tests/fixtures/http/ 下的录制响应提供，不依赖实时网络。
"""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from core.tester import All, Contains, Match, Not, Tester, func_case
from core.tester.mock.session import MockMessageSession
from core.utils.url_audit import GlobalURLAllowlist, GlobalURLBlocklist

START_WIKI = "~wiki set https://zh.minecraft.wiki/api.php"
_original_mock_session_init = MockMessageSession.async_init


async def _init_url_manager_session(self, msg):
    await _original_mock_session_init(self, msg)
    self.session_info.use_url_manager = True


@func_case
async def test_wiki_set_url_policy(tester: Tester):
    """wiki set 应以规范 API 端点的全局 URL 策略作为唯一认证来源。"""
    from modules.wiki.database.models import WikiTargetInfo

    api = "https://zh.minecraft.wiki/api.php"
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
            patch.object(MockMessageSession, "async_init", _init_url_manager_session),
        ):
            GlobalURLAllowlist.clear_cache()
            GlobalURLBlocklist.clear_cache()
            try:
                GlobalURLBlocklist.add_user_rule(api)
                await tester.integrate(
                    START_WIKI,
                    Contains("处于阻止列表中"),
                    "wiki set 应拦截全局 URL 阻止列表中的 API",
                )
                blocked_target = await WikiTargetInfo.get_by_target_id("TEST|Console|0")
                await tester.test(lambda: blocked_target.api_link is None, "阻止列表中的 Wiki 不应写入默认绑定")

                GlobalURLBlocklist.remove_user_rule(api)
                await tester.integrate(
                    START_WIKI,
                    Contains("API 端点当前没有加入机器人的全局 URL 允许列表"),
                    "wiki set 应提示 API 未加入全局 URL 允许列表",
                )
                untrusted_target = await WikiTargetInfo.get_by_target_id("TEST|Console|0")
                await tester.test(lambda: untrusted_target.api_link == api, "未认证 Wiki API 提示后仍应完成绑定")

                GlobalURLAllowlist.add_user_rule(api)
                await tester.integrate(
                    START_WIKI,
                    All(
                        Contains("成功设置默认 Wiki"),
                        Not(Contains("没有加入机器人的全局 URL 允许列表")),
                    ),
                    "全局 URL 允许列表中的 API 应作为可信 Wiki",
                )

                GlobalURLBlocklist.add_user_rule(api)
                blocked_message = "失败：Minecraft Wiki (zh) 处于阻止列表中。"
                with (
                    patch("modules.wiki.utils.wikilib.WikiLib.parse_page_info", side_effect=AssertionError),
                    patch("modules.wiki.utils.wikilib.WikiLib.search_page", side_effect=AssertionError),
                ):
                    await tester.integrate(
                        "~wiki Minecraft",
                        Match(blocked_message),
                        "已绑定 Wiki 的 API 进入全局阻止列表后应拒绝页面查询",
                    )
                    await tester.integrate(
                        "~wiki search Minecraft",
                        Match(blocked_message),
                        "已绑定 Wiki 的 API 进入全局阻止列表后应拒绝搜索",
                    )
            finally:
                GlobalURLAllowlist.clear_cache()
                GlobalURLBlocklist.clear_cache()
    return tester


@func_case
async def test_wiki_search(tester: Tester):
    """wiki search 搜索测试"""
    await tester.integrate(START_WIKI, Contains("成功设置默认 Wiki"), "设置 Wiki")
    await tester.integrate("~wiki search Minecraft", Contains("搜索结果"), "wiki search 应返回搜索结果")
    return tester


@func_case
async def test_wiki_iw_manage(tester: Tester):
    """wiki iw 管理测试"""
    await tester.integrate("~wiki iw list", Contains("Interwiki"), "wiki iw list 应显示列表")
    return tester


@func_case
async def test_wiki_headers_manage(tester: Tester):
    """wiki headers 管理测试"""
    await tester.integrate(START_WIKI, Contains("成功设置默认 Wiki"), "设置 Wiki")
    await tester.integrate("~wiki headers show", Contains("请求标头"), "wiki headers show 应显示标头")
    return tester


@func_case
async def test_wiki_prefix_manage(tester: Tester):
    """wiki prefix 管理测试"""
    await tester.integrate(START_WIKI, Contains("成功设置默认 Wiki"), "设置 Wiki")
    await tester.integrate("~wiki prefix set Test", Contains("前缀"), "wiki prefix set 应提示设置结果")
    await tester.integrate("~wiki prefix reset", Contains("重置"), "wiki prefix reset 应提示重置")
    return tester


@func_case
async def test_wiki_not_found(tester: Tester):
    """wiki 不存在页面测试"""
    await tester.integrate(START_WIKI, Contains("成功设置默认 Wiki"), "设置 Wiki")
    await tester.integrate("~wiki nonexistent_page_xyz_12345", Contains("未找到"), "不存在的页面应提示未找到")
    return tester


@func_case
async def test_wiki_start_wiki_not_set(tester: Tester):
    """未设置默认 Wiki 提示测试

    推荐绑定的按钮只在 QQ 官方机器人上附加，测试会话的客户端名恒为 TEST，
    故此处只求证提示本身照常发出，按钮相关的判据见 tests/unit/test_wiki_recommend.py。
    """
    await tester.integrate("~wiki Minecraft", Contains("没有设置默认 Wiki"), "wiki 查询应提示未设置")
    await tester.integrate("~wiki search Minecraft", Contains("没有设置默认 Wiki"), "wiki search 应提示未设置")
    return tester
