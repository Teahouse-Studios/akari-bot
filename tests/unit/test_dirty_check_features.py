"""bots/*/features 单元测试 - 平台能力开关的声明与传递（需要数据库）。"""

import ast
import pkgutil
from pathlib import Path

import bots
from core.alive import Alive
from core.builtins.bot import Bot
from core.builtins.converter import converter
from core.builtins.session.features import Features
from core.builtins.session.internal import FetchedMessageSession
from core.tester import func_case, Tester

FLAG = "require_check_dirty_words"


def _features_sources() -> dict[str, str]:
    """
    读取各平台 features 模块的源码。
    """
    sources = {}
    for m in pkgutil.iter_modules(bots.__path__):
        path = Path(bots.__path__[0]) / m.name / "features.py"
        if path.is_file():
            sources[m.name] = path.read_text(encoding="utf-8")
    return sources


def _reads_config(node: ast.AST) -> bool:
    """
    判断表达式中是否存在对配置模板的属性访问，如 ``CoreConfig.enable_dirty_check``。
    """
    return any(
        isinstance(sub, ast.Attribute) and isinstance(sub.value, ast.Name) and sub.value.id.endswith("Config")
        for sub in ast.walk(node)
    )


def _dead_config_names(source: str) -> list[str]:
    """
    找出模块顶层由配置取值、却从未被读取的名字。

    只看由配置取值的赋值，而非全部顶层赋值：模块自身导出的能力实例也是一个顶层赋值，
    它在本文件内无人读取属于正常，一并计入会把每个平台都误判为存在哑变量。
    """
    tree = ast.parse(source)
    assigned = {
        target.id
        for node in tree.body
        if isinstance(node, ast.Assign) and _reads_config(node.value)
        for target in node.targets
        if isinstance(target, ast.Name)
    }
    loaded = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)}
    return sorted(assigned - loaded)


def _test_no_dead_config_read_in_features():
    """测试平台能力 - features 模块不得存在读了配置却没落到字段上的哑变量"""
    try:
        # onebot 曾在顶层算出 dirty_word_check 与 use_url_manager 却没传给 Features，
        # 两个字段静默沿用基类的 False，该平台的文字过滤与 URLManager 因此整体失效。
        return not {name: dead for name, source in _features_sources().items() if (dead := _dead_config_names(source))}

    except Exception:
        return False


async def _test_flag_reaches_fetched_session():
    """测试文字过滤 - 平台声明的开关须传递到主动推送会话上"""
    alive = Alive.values.copy()
    try:
        Alive.values.clear()
        # 主动推送的会话没有触发消息，能力标志只能从保活信号里带过来，
        # wikilog 等模块的 check() 正是据此判断要不要过滤。
        for client, flag in (("DIRTYON", True), ("DIRTYOFF", False)):
            features = Features(**{FLAG: flag})
            Alive.refresh_alive(
                client,
                target_prefix_list=[f"{client}|Group"],
                sender_prefix_list=[client],
                ctx_slot_index=1,
                features=converter.structure(converter.unstructure(features, Features), Features),
            )

        for client, flag in (("DIRTYON", True), ("DIRTYOFF", False)):
            fetched = await Bot.fetch_target(f"{client}|Group|1", create=True)
            if not fetched:
                return False
            session = await FetchedMessageSession.from_session_info(fetched)
            if getattr(session.session_info, FLAG) is not flag:
                return False
        return True

    except Exception:
        return False
    finally:
        Alive.values.clear()
        Alive.values.update(alive)


@func_case
async def test_dirty_check_features(tester: Tester):
    """bots.features: 平台能力开关测试"""
    await tester.test(_test_no_dead_config_read_in_features, "无哑变量测试")
    await tester.test(_test_flag_reaches_fetched_session, "开关传递到主动推送会话测试")

    return tester
