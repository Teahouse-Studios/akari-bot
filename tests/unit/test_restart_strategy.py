"""Git 变更范围对应的重启策略测试。"""

from unittest.mock import MagicMock, patch

from core.queue import client as queue_client
from core.restart import (
    RESTART_ALL_EXIT_CODE,
    RESTART_PROCESS_EXIT_CODE,
    RestartScope,
    classify_restart_paths,
    get_bot_client_name,
    parse_git_diff_paths,
)
from core.tester import func_case, Tester


BOTS = {"discord", "kook", "matrix", "onebot", "qqbot", "telegram", "web"}


def _plan_is(paths, scope, bots=()):
    plan = classify_restart_paths(paths, BOTS)
    return plan.scope == scope and plan.bots == bots


async def _targeted_restart_is_delayed():
    loop = MagicMock()
    with patch("core.queue.client.asyncio.get_running_loop", return_value=loop):
        result = await queue_client.restart_client(None, {})
    scheduled = loop.call_later.call_args.args
    return (
        result == {"success": True}
        and scheduled[0] == 1
        and scheduled[1] is queue_client.os._exit
        and scheduled[2] == RESTART_PROCESS_EXIT_CODE
    )


@func_case
async def test_restart_strategy(tester: Tester):
    """core.restart: Git 变更分类测试。"""
    await tester.test(
        lambda: _plan_is(["modules/wiki/__init__.py", "modules/core/help.py"], RestartScope.SERVER),
        "仅模块变更只重启 server",
    )
    await tester.test(
        lambda: _plan_is(["core/loader.py"], RestartScope.ALL),
        "core 变更重启全部子进程",
    )
    await tester.test(
        lambda: _plan_is(["bots/discord/bot.py"], RestartScope.BOTS, ("discord",)),
        "单个平台变更只重启对应 bot",
    )
    await tester.test(
        lambda: _plan_is(
            ["bots/telegram/context.py", "bots/discord/buttons.py"],
            RestartScope.BOTS,
            ("discord", "telegram"),
        ),
        "多个平台变更只重启对应 bot",
    )
    await tester.test(
        lambda: _plan_is(["bot.py", "modules/wiki/__init__.py"], RestartScope.MANUAL),
        "bot.py 变更拒绝内部重启",
    )
    await tester.test(
        lambda: _plan_is([".\\modules\\wiki\\__init__.py"], RestartScope.SERVER),
        "Windows 路径可正确归一化",
    )
    await tester.test(
        lambda: _plan_is(["modules/wiki/config.py"], RestartScope.ALL),
        "模块配置模板变更须经过 pre-init",
    )
    await tester.test(
        lambda: _plan_is(["bots/discord/config.py"], RestartScope.ALL),
        "平台配置模板变更须经过 pre-init",
    )
    await tester.test(
        lambda: _plan_is(["bots/discord/info.py"], RestartScope.ALL),
        "平台队列名称变更须同时重启两侧",
    )
    await tester.test(
        lambda: _plan_is(["bots/discord/locales/zh_cn.json"], RestartScope.ALL),
        "平台语言文件变更同时影响 server",
    )
    await tester.test(
        lambda: _plan_is(["modules/wiki/__init__.py", "bots/discord/bot.py"], RestartScope.ALL),
        "混合目录变更保守重启全部子进程",
    )
    await tester.test(
        lambda: _plan_is(["pyproject.toml"], RestartScope.ALL) and _plan_is([], RestartScope.ALL),
        "根目录或空变更保持全量重启",
    )
    await tester.test(
        lambda: parse_git_diff_paths("bot.py\0bots/discord/bot.py\0") == ("bot.py", "bots/discord/bot.py"),
        "NUL 分隔的 Git 路径解析",
    )
    await tester.test(
        lambda: get_bot_client_name("onebot") == "QQ" and get_bot_client_name("qqbot") == "QQBot",
        "平台目录映射到队列客户端名称",
    )
    await tester.test(
        lambda: (
            0 < RESTART_ALL_EXIT_CODE < 256
            and 0 < RESTART_PROCESS_EXIT_CODE < 256
            and RESTART_ALL_EXIT_CODE != RESTART_PROCESS_EXIT_CODE
        ),
        "重启退出码在可移植范围内且互不冲突",
    )
    await tester.test(_targeted_restart_is_delayed, "目标 bot 在队列动作完成后延迟退出")

    return tester
