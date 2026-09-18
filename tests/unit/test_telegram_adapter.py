"""Telegram 消息入口的可选字段兼容测试。"""

import importlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from bots.telegram.config import AiogramConfig, AiogramSecretConfig
from core.builtins.message.chain import MessageChain
from core.builtins.session.info import SessionInfo
from core.tester import Tester, func_case


def _load_telegram_bot_module():
    with (
        patch.object(AiogramConfig, "enable", False, create=True),
        patch.object(
            AiogramSecretConfig,
            "telegram_token",
            "123456:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij",
            create=True,
        ),
    ):
        return importlib.import_module("bots.telegram.bot")


async def _test_document_without_mime_type_is_ignored() -> bool:
    telegram_bot = _load_telegram_bot_module()
    message = SimpleNamespace(
        audio=None,
        photo=None,
        video=None,
        document=SimpleNamespace(file_id="document", mime_type=None),
        caption=None,
        text=None,
    )
    get_file = AsyncMock(return_value=SimpleNamespace(file_path="documents/file.bin"))
    with patch.object(telegram_bot.aiogram_bot, "get_file", new=get_file):
        chain = await telegram_bot.to_message_chain(message)
    return not chain.values


async def _test_message_without_from_user_is_ignored() -> bool:
    telegram_bot = _load_telegram_bot_module()
    message = SimpleNamespace(
        chat=SimpleNamespace(type="supergroup", id=-10001),
        from_user=None,
    )
    assign = AsyncMock()
    process = AsyncMock()
    with (
        patch.object(telegram_bot.SessionInfo, "assign", new=assign),
        patch.object(telegram_bot.Bot, "process_message", new=process),
    ):
        result = await telegram_bot.msg_handler(message)
    return result is None and assign.await_count == 0 and process.await_count == 0


async def _test_send_failure_returns_empty() -> bool:
    _load_telegram_bot_module()
    telegram_context = importlib.import_module("bots.telegram.context")
    session = SessionInfo(
        target_id="Telegram|Group|-10001",
        target_from="Telegram|Group",
        sender_id="Telegram|Client|1",
        sender_from="Telegram|Client",
        client_name="Telegram",
        session_id="telegram-send-failure",
    )
    with patch.object(
        telegram_context,
        "execute_telegram_operations",
        new=AsyncMock(side_effect=RuntimeError("send failed")),
    ):
        try:
            result = await telegram_context.TelegramContextManager.send_message(
                session,
                MessageChain.assign("hello"),
                quote=False,
            )
        except Exception:
            return False
    return result == []


@func_case
async def test_telegram_adapter(tester: Tester):
    await tester.test(_test_document_without_mime_type_is_ignored, "Telegram 未知 MIME 文档不崩溃")
    await tester.test(_test_message_without_from_user_is_ignored, "Telegram 无发送者消息安全忽略")
    await tester.test(_test_send_failure_returns_empty, "Telegram 发送异常返回空消息 ID")
    return tester
