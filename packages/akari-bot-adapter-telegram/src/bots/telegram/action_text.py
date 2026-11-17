"""Telegram Inline Mode ActionText 交互。"""

import hashlib

from aiogram import types
from aiogram.types import InlineQueryResultArticle, InputTextMessageContent

from core.config.base import BaseConfig
from core.i18n import Locale


def is_own_inline_message(message: types.Message, bot_id: int) -> bool:
    """判断消息是否由当前机器人通过 Inline Mode 代发。"""
    return bool(message.via_bot and message.via_bot.id == bot_id)


def can_use_inline_action_text(target_from: str, supports_inline_queries: bool) -> bool:
    """频道不支持在当前聊天打开 Inline Query，须改用复制按钮。"""
    return supports_inline_queries and not target_from.endswith("|Channel")


def build_action_text_inline_results(query: str) -> list[InlineQueryResultArticle]:
    """为用户编辑后的命令构造唯一一个“发送”结果。"""
    if not query:
        return []
    result_id = hashlib.sha256(query.encode("utf-8")).hexdigest()[:32]
    locale = Locale(BaseConfig.default_locale)
    return [
        InlineQueryResultArticle(
            id=result_id,
            title=locale.t("message.action_text.send"),
            description=query,
            input_message_content=InputTextMessageContent(message_text=query, parse_mode=None),
        )
    ]


async def handle_action_text_inline_query(inline_query: types.InlineQuery) -> None:
    """响应 ActionText 打开的 Inline Query。"""
    await inline_query.answer(
        build_action_text_inline_results(inline_query.query),
        cache_time=0,
        is_personal=True,
    )
