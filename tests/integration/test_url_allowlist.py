"""全局 URL 允许列表命令集成测试。"""

import time
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, patch

from core.builtins.message.elements import ImageElement
from core.tester import Contains, Empty, Exist, Tester, func_case
from core.utils.url_audit import GlobalURLAllowlist, URLRuleError, match_regex_rules, validate_regex_pattern


@func_case
async def test_url_allowlist_commands(tester: Tester):
    with TemporaryDirectory() as temp_dir:
        directory = Path(temp_dir)
        with (
            patch.object(GlobalURLAllowlist, "directory", directory),
            patch.object(GlobalURLAllowlist, "builtin_path", directory / "global.txt"),
            patch.object(GlobalURLAllowlist, "user_path", directory / "user.txt"),
        ):
            directory.mkdir(parents=True, exist_ok=True)
            (directory / "global.txt").write_text("https://repo.example.test/release\n", encoding="utf-8")
            GlobalURLAllowlist.clear_cache()
            await tester.integrate(
                "~url allowlist query https://repo.example.test/release",
                Contains("主仓规则"),
                "主仓同步规则应被识别并标记来源",
            )
            await tester.integrate(
                "~url allowlist add https://repo.example.test/release",
                Contains("规则已存在"),
                "用户文件不应重复覆盖主仓规则",
            )
            await tester.integrate(
                "~url allowlist add https://example.test/docs/1",
                Contains("已将规则加入用户自定义 URL 允许列表"),
                "应能通过命令添加精确 URL 规则",
            )
            await tester.integrate(
                "~url allowlist query https://example.test/docs/1",
                Contains("已被以下全局规则放行"),
                "精确 URL 规则应立即生效",
            )
            await tester.integrate(
                r"~url allowlist add-regex https://[a-z]{2}\.example\.test/docs/[0-9]+",
                Contains("已将规则加入用户自定义 URL 允许列表"),
                "应能通过命令添加正则 URL 规则",
            )
            await tester.integrate(
                "~url allowlist query https://zh.example.test/docs/42",
                Contains("已被以下全局规则放行"),
                "正则 URL 规则应立即生效",
            )
            render = AsyncMock(return_value=["https://example.test/allowlist.png"])
            with patch("modules.core.su_utils.image_table_render", new=render):
                await tester.integrate(
                    "~url allowlist list",
                    Exist(ImageElement),
                    "允许列表应渲染为图片表格",
                )
            await tester.test(
                lambda: (
                    render.await_count == 1
                    and render.await_args.args[0].headers == ["来源", "类型", "规则"]
                    and ["主仓规则", "精确 URL", "https://repo.example.test/release"] in render.await_args.args[0].data
                    and ["用户规则", "正则表达式", "https://[a-z]{2}.example.test/docs/[0-9]+"]
                    in render.await_args.args[0].data
                ),
                "允许列表图片表格应包含来源、类型与规则",
            )
            with patch("modules.core.su_utils.image_table_render", new=AsyncMock(return_value=None)):
                await tester.integrate(
                    "~url allowlist list",
                    Empty(),
                    "WebRender 不可用时允许列表命令不得发出任何内容",
                )
            await tester.integrate(
                "~url allowlist add-regex .*",
                Contains("匹配范围过宽"),
                "过宽正则表达式应被拒绝",
            )
            await tester.integrate(
                "~url allowlist remove https://example.test/docs/1",
                Contains("已从用户自定义 URL 允许列表删除规则"),
                "应能通过命令删除精确 URL 规则",
            )
            await tester.test(lambda: (directory / "user.txt").exists(), "命令配置应写入 user.txt")

            def rejects_unsafe_regex():
                try:
                    validate_regex_pattern(r"https://example\.test/(a+)\1")
                except URLRuleError as exc:
                    return exc.reason == "unsafe_regex"
                return False

            await tester.test(rejects_unsafe_regex, "反向引用正则应被拒绝")

            def catastrophic_regex_is_bounded():
                started = time.monotonic()
                matched = match_regex_rules(
                    "https://example.test/" + "a" * 4000 + "!",
                    (r"https://example\.test/(a+)+$",),
                )
                return not matched and time.monotonic() - started < 0.2

            await tester.test(catastrophic_regex_is_bounded, "灾难性回溯正则应受执行超时约束")
    GlobalURLAllowlist.clear_cache()
    return tester
