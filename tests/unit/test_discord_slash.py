"""Discord 斜线命令注册结构的单元测试。

Discord 在批量注册时会校验命令载荷，同级名称重复将导致整批注册被拒绝
（HTTP 400，错误码 50035），表现为适配器启动时 on_connect 抛出异常。
由于校验发生在 Discord 服务端，本地无从察觉，故在此对载荷结构做静态断言。
"""

import importlib
import pkgutil

from core.logger import Logger
from core.tester import func_case, Tester

# 处理函数统一以 _ 命名，装饰器若遗漏 name 参数，py-cord 将回退使用函数名作为命令名。
PLACEHOLDER_NAME = "_"


def _load_slash_payload() -> list[dict]:
    """导入全部 Discord 斜线命令模块，并取回待注册命令的载荷。

    :return: 每个顶层命令经 to_dict() 转换后的载荷列表。
    """
    import bots.discord.slash as slash_modules
    from bots.discord.client import discord_bot

    for submodule in pkgutil.iter_modules(slash_modules.__path__):
        if submodule.name in ["context", "parser"]:
            continue
        importlib.import_module(f"{slash_modules.__name__}.{submodule.name}")

    return [command.to_dict() for command in discord_bot.pending_application_commands]


def _iter_sibling_groups(nodes: list[dict], path: tuple[str, ...] = ()):
    """递归遍历命令载荷，逐层产出同级节点的名称集合。

    :param nodes: 当前层级的节点列表，即顶层命令或某个命令的 options。
    :param path: 当前层级在命令树中的路径。
    :return: (路径, 该层级全部节点名称) 二元组的生成器。
    """
    yield path, [node["name"] for node in nodes]
    for node in nodes:
        options = node.get("options") or []
        if options:
            yield from _iter_sibling_groups(options, path + (node["name"],))


def _test_no_placeholder_command_name():
    """命令与选项均不得沿用占位函数名，否则说明装饰器遗漏了 name 参数"""
    offenders = []
    for path, names in _iter_sibling_groups(_load_slash_payload()):
        offenders.extend(" ".join(path + (name,)) for name in names if name == PLACEHOLDER_NAME)

    if offenders:
        Logger.error(f"Slash commands using placeholder name: {offenders}")
    return not offenders


def _test_no_duplicate_sibling_names():
    """同级的命令、子命令与选项名称必须互不重复，否则 Discord 将拒绝整批注册"""
    conflicts = []
    for path, names in _iter_sibling_groups(_load_slash_payload()):
        duplicated = sorted({name for name in names if names.count(name) > 1})
        if duplicated:
            conflicts.append((" ".join(path) or "<root>", duplicated))

    if conflicts:
        Logger.error(f"Slash commands with duplicated sibling names: {conflicts}")
    return not conflicts


@func_case
async def test_discord_slash(tester: Tester):
    """bots.discord.slash: 斜线命令注册结构测试"""
    await tester.test(_test_no_placeholder_command_name, "命令名未沿用占位函数名测试")
    await tester.test(_test_no_duplicate_sibling_names, "同级命令名不重复测试")

    return tester
