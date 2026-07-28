"""features 命令集成测试 - 当前会话与主动获取会话的特性对照。"""

from unittest.mock import patch

import core.builtins.bot as bot_module
from core.builtins.session.features import Features
from core.tester import func_case, ContainsAll, Tester
from core.utils.session import inject_features


@func_case
async def test_features(tester: Tester):
    """features 命令测试"""
    await tester.integrate(
        "~features",
        ContainsAll("特性标志", "support_image", "require_check_dirty_words"),
        "features 应逐项列出会话的特性标志",
    )

    real_fetch = bot_module.Bot.fetch_target

    async def degraded_fetch(target_id, sender_id=None, create=False):
        """主动获取的会话缺少若干能力，模拟保活信号带来的能力与当前会话不一致。"""
        fetched = await real_fetch(target_id, sender_id, create)
        if not fetched:
            return fetched
        return inject_features(fetched, Features(support_image=True, require_enable_modules=False))

    with patch.object(bot_module.Bot, "fetch_target", degraded_fetch):
        await tester.integrate(
            "~features",
            ContainsAll("*support_image", "*require_enable_modules", "2 项两侧不一致"),
            "features 应标出两侧不一致的特性并给出计数",
        )

    async def failed_fetch(target_id, sender_id=None, create=False):
        return None

    with patch.object(bot_module.Bot, "fetch_target", failed_fetch):
        await tester.integrate(
            "~features",
            ContainsAll("无法主动获取", "未知"),
            "features 在主动获取失败时应把右侧一列标为未知",
        )

    return tester
