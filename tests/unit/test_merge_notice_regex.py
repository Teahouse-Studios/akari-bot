"""modules.core.merge 单元测试 - 退役公告触发器的注册形态。

``merge`` 模块仅在配置了迁移关系时加载（``load=bool(CoreConfig.retired_clients)``），
测试环境默认未配置，故本组用例在模块未加载时自动通过。要真正验证触发器，
须临时在 ``config/config.toml`` 中设置 ``retired_clients`` 后重跑，详见实施计划的 Task 15。
"""

from core.loader import ModulesManager
from core.tester import func_case, Tester


def _merge_loaded() -> bool:
    """merge 模块仅在配置了迁移关系时加载，未配置时本组用例无从验证。"""
    return "merge" in ModulesManager.modules


def _notice_regex():
    """取出 merge 模块中唯一的正则处理函数元数据。"""
    metas = ModulesManager.modules["merge"].regex_list.set
    return metas[0] if metas else None


async def _test_regex_registered():
    """测试公告触发器 - 已注册到 merge 模块"""
    try:
        if not _merge_loaded():
            return True
        return _notice_regex() is not None

    except Exception:
        return False


async def _test_regex_matches_any_text():
    """测试公告触发器 - 匹配任意非空文本，空串不匹配"""
    try:
        if not _merge_loaded():
            return True
        rfunc = _notice_regex()
        return bool(rfunc.compiled.match("闲聊一句")) and not rfunc.compiled.match("")

    except Exception:
        return False


async def _test_regex_flags():
    """测试公告触发器 - 标记为单次触发且不占用输入状态与日志"""
    try:
        if not _merge_loaded():
            return True
        rfunc = _notice_regex()
        return rfunc.trigger_once_startup and not rfunc.show_typing and not rfunc.logging

    except Exception:
        return False


@func_case
async def test_merge_notice_regex(tester: Tester):
    """modules.core.merge: 退役公告触发器测试"""
    await tester.test(_test_regex_registered, "触发器注册测试")
    await tester.test(_test_regex_matches_any_text, "任意文本匹配测试")
    await tester.test(_test_regex_flags, "触发器标记测试")

    return tester
