"""support_button 特性单元测试。

按钮此前由「客户端名为 QQBot 且支持 Markdown」这一组合就地判定，散落在 wiki 各处共九处。
摊平为独立标志后，新增支持按钮的平台只需在自己的 features.py 中声明，无须回头改动模块。

取值须跟随 qq_use_markdown 而非恒为真：按钮只在 send_msg_markdown() 中下发，
关闭该配置时消息走纯文本路径，模块侧构造的按钮数据会被平台默默丢弃。
"""

from attr import evolve

from bots.discord.features import features as discord_features
from bots.qqbot.config import QQBotConfig
from bots.qqbot.features import features as qqbot_features
from bots.telegram.features import features as telegram_features
from core.builtins.session.features import Features
from core.builtins.session.info import SessionInfo
from core.tester import func_case, Tester


def _test_defaults_to_false():
    """按钮是少数平台才有的能力，默认不具备。"""
    return Features().support_button is False


def _test_can_be_enabled():
    """平台可经 evolve 声明该能力。"""
    return evolve(Features(), support_button=True).support_button is True


def _test_session_info_declares_field():
    """SessionInfo 须声明同名字段，否则该项无法随会话序列化传至 server 进程。"""
    return "support_button" in {x.name for x in SessionInfo.__attrs_attrs__}


async def _test_injects_into_session():
    """特性须能注入会话。此处取 True 而非默认的 False，默认值相同时测不出遗漏。"""
    session_info = await SessionInfo.assign(
        target_id="TEST|Group|support_button",
        target_from="TEST|Group",
        client_name="TEST",
        sender_id="TEST|1",
        features=Features(support_button=True),
    )
    return session_info.support_button is True


def _test_qqbot_follows_markdown_config():
    """QQBot 的按钮能力须跟随 qq_use_markdown，与 support_action_text 取同一判据。"""
    return qqbot_features.support_button is QQBotConfig.qq_use_markdown


def _test_discord_enables_button():
    """Discord 须声明原生按钮能力。"""
    return discord_features.support_button is True


def _test_telegram_enables_button():
    """Telegram 须声明原生按钮能力。"""
    return telegram_features.support_button is True


@func_case
async def test_support_button(tester: Tester):
    """core: support_button 特性"""
    await tester.test(_test_defaults_to_false, "默认不具备按钮能力")
    await tester.test(_test_can_be_enabled, "可声明按钮能力")
    await tester.test(_test_session_info_declares_field, "SessionInfo 声明该字段")
    await tester.test(_test_injects_into_session, "特性可注入会话")
    await tester.test(_test_qqbot_follows_markdown_config, "QQBot 跟随 Markdown 配置")
    await tester.test(_test_discord_enables_button, "Discord 开启按钮能力")
    await tester.test(_test_telegram_enables_button, "Telegram 开启按钮能力")
    return tester
