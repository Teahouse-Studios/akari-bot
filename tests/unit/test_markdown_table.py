"""各平台 Markdown 表格能力声明测试。"""

from bots.discord.features import features as discord_features
from bots.qqbot.config import QQBotConfig
from bots.qqbot.features import features as qqbot_features
from bots.telegram.features import features as telegram_features
from core.logger import Logger
from core.tester import func_case, Tester


def _test_discord_disables_markdown_table() -> bool:
    """Discord 保留普通 Markdown，但不声明表格能力。"""
    if discord_features.support_markdown is not True:
        Logger.error("Discord should keep ordinary markdown support")
        return False
    if discord_features.support_markdown_table is not False:
        Logger.error("Discord should disable markdown tables")
        return False
    return True


def _test_telegram_disables_markdown_table() -> bool:
    """Telegram 不声明 Markdown 表格能力。"""
    if telegram_features.support_markdown_table is not False:
        Logger.error("Telegram should disable markdown tables")
        return False
    return True


def _test_qqbot_follows_markdown_config() -> bool:
    """QQBot 的表格能力随其 Markdown 配置启停。"""
    if qqbot_features.support_markdown_table is not QQBotConfig.qq_use_markdown:
        Logger.error("QQBot should tie markdown table support to qq_use_markdown")
        return False
    return True


@func_case
async def test_markdown_table(tester: Tester):
    """平台 Markdown 表格能力测试。"""
    await tester.test(_test_discord_disables_markdown_table, "Discord 关闭 Markdown 表格测试")
    await tester.test(_test_telegram_disables_markdown_table, "Telegram 关闭 Markdown 表格测试")
    await tester.test(_test_qqbot_follows_markdown_config, "QQBot Markdown 表格能力配置测试")

    return tester
