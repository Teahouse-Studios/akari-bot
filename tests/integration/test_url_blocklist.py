"""全局 URL 阻止列表命令集成测试。"""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, patch

from core.builtins.message.elements import ImageElement
from core.tester import Contains, Empty, Exist, Tester, func_case
from core.utils.url_audit import GlobalURLBlocklist


@func_case
async def test_url_blocklist_commands(tester: Tester):
    with TemporaryDirectory() as temp_dir:
        directory = Path(temp_dir)
        with (
            patch.object(GlobalURLBlocklist, "directory", directory),
            patch.object(GlobalURLBlocklist, "builtin_path", directory / "global.txt"),
            patch.object(GlobalURLBlocklist, "user_path", directory / "user.txt"),
        ):
            directory.mkdir(parents=True, exist_ok=True)
            (directory / "global.txt").write_text("https://repo-blocked.example.test/release\n", encoding="utf-8")
            GlobalURLBlocklist.clear_cache()
            await tester.integrate(
                "~url-audit blocklist query https://repo-blocked.example.test/release",
                Contains("全局规则"),
                "全局阻止列表规则应被识别并标记来源",
            )
            await tester.integrate(
                "~url-audit blocklist add https://repo-blocked.example.test/release",
                Contains("规则已存在"),
                "用户文件不应重复覆盖全局阻止列表规则",
            )
            await tester.integrate(
                "~url-audit blocklist add https://blocked.example.test/docs/1",
                Contains("已将规则加入用户自定义 URL 阻止列表"),
                "应能通过命令添加精确 URL 阻止列表规则",
            )
            await tester.integrate(
                "~url-audit blocklist query https://blocked.example.test/docs/1",
                Contains("已被以下全局规则拦截"),
                "精确 URL 阻止列表规则应立即生效",
            )
            await tester.integrate(
                r"~url-audit blocklist add-regex https://blocked-[a-z]{2}\.example\.test/docs/[0-9]+",
                Contains("已将规则加入用户自定义 URL 阻止列表"),
                "应能通过命令添加正则 URL 阻止列表规则",
            )
            await tester.integrate(
                "~url-audit blocklist query https://blocked-zh.example.test/docs/42",
                Contains("已被以下全局规则拦截"),
                "正则 URL 阻止列表规则应立即生效",
            )
            await tester.integrate(
                "~url-audit blocklist query https://blocked-zhXexampleYtest/docs/42",
                Contains("未被全局 URL 阻止列表拦截"),
                "转义点号不得被改写为可匹配任意字符的通配符",
            )
            await tester.test(
                lambda: (
                    r"regex:https://blocked-[a-z]{2}\.example\.test/docs/[0-9]+"
                    in (directory / "user.txt").read_text(encoding="utf-8").splitlines()
                ),
                "命令写入 user.txt 时应保留正则反斜杠",
            )
            render = AsyncMock(return_value=["https://example.test/blocklist.png"])
            with patch("modules.core.su_utils.image_table_render", new=render):
                await tester.integrate(
                    "~url-audit blocklist list",
                    Exist(ImageElement),
                    "阻止列表应渲染为图片表格",
                )
            await tester.test(
                lambda: (
                    render.await_count == 1
                    and render.await_args.args[0].headers == ["来源", "类型", "规则"]
                    and ["全局规则", "精确 URL", "https://repo-blocked.example.test/release"]
                    in render.await_args.args[0].data
                    and [
                        "用户规则",
                        "正则表达式",
                        r"https://blocked-[a-z]{2}\.example\.test/docs/[0-9]+",
                    ]
                    in render.await_args.args[0].data
                ),
                "阻止列表图片表格应包含来源、类型与规则",
            )
            with patch("modules.core.su_utils.image_table_render", new=AsyncMock(return_value=None)):
                await tester.integrate(
                    "~url-audit blocklist list",
                    Empty(),
                    "WebRender 不可用时阻止列表命令不得发出任何内容",
                )
            await tester.integrate(
                "~url-audit blocklist add-regex .*",
                Contains("匹配范围过宽"),
                "阻止列表过宽正则表达式应被拒绝",
            )
            await tester.integrate(
                "~url-audit blocklist remove https://blocked.example.test/docs/1",
                Contains("已从用户自定义 URL 阻止列表删除规则"),
                "应能通过命令删除精确 URL 阻止列表规则",
            )
            await tester.test(lambda: (directory / "user.txt").exists(), "阻止列表命令配置应写入 user.txt")
    GlobalURLBlocklist.clear_cache()
    return tester
