"""modules.core.admin_tools.alias 单元测试 - 自定义别名改写。"""

from types import SimpleNamespace

from core.builtins.parser.hooks import HookPoint, dispatch_parser_hook
from core.tester import Tester, func_case
from modules.core.admin_tools.alias import transform_alias


def _test_simple_alias():
    return transform_alias("~h wiki", {"~h": "help"}, "~") == "~help wiki"


def _test_placeholder_alias():
    aliases = {"~w ${title}": "wiki ${title}"}
    return transform_alias("~w AkariBot", aliases, "~") == "~wiki AkariBot"


def _test_alias_miss():
    return transform_alias("~version", {"~h": "help"}, "~") == "~version"


async def _test_alias_hook_commits_rewrite():
    msg = SimpleNamespace(
        trigger_msg="~w AkariBot",
        session_info=SimpleNamespace(
            target_from="TEST",
            client_name="TEST",
            prefixes=["~"],
            target_union_info=SimpleNamespace(target_data={"command_alias": {"~w ${title}": "wiki ${title}"}}),
        ),
    )
    await dispatch_parser_hook(HookPoint.MESSAGE_NORMALIZED, msg)
    return msg.trigger_msg == "~wiki AkariBot"


@func_case
async def test_parser_routing(tester: Tester):
    await tester.test(_test_simple_alias, "简单别名改写测试")
    await tester.test(_test_placeholder_alias, "占位符别名改写测试")
    await tester.test(_test_alias_miss, "未匹配别名保持原文测试")
    await tester.test(_test_alias_hook_commits_rewrite, "别名 hook 提交触发文本测试")
    return tester
