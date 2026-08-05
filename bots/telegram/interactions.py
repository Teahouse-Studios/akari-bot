"""Telegram 按钮点击回流。"""

from aiogram import types

from bots.telegram.buttons import remove_selected_button
from bots.telegram.info import client_name, sender_prefix, target_prefix
from core.builtins.bot import Bot
from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import Plain
from core.builtins.session.info import SessionInfo
from core.config.base import BaseConfig
from core.i18n import Locale
from core.logger import Logger
from core.utils.button_runtime import (
    BUTTON_TOKEN_PREFIX,
    ButtonConsumeStatus,
    consume_button,
    normalize_button_payload,
)

_BUTTON_ERROR_KEYS = {
    ButtonConsumeStatus.INVALID: "message.button.invalid",
    ButtonConsumeStatus.EXPIRED: "message.button.expired",
    ButtonConsumeStatus.FORBIDDEN: "message.button.forbidden",
    ButtonConsumeStatus.USED: "message.button.used",
}


def _get_bot_id() -> str:
    from bots.telegram.client import aiogram_bot

    return str(aiogram_bot.id)


async def handle_button_callback(callback: types.CallbackQuery, ctx_slot: int | None = None) -> None:
    """处理 Telegram 按钮点击并重新进入消息流程。"""
    if not (callback.data or "").startswith(BUTTON_TOKEN_PREFIX):
        return

    locale = Locale(BaseConfig.default_locale)
    if callback.message is None:
        await callback.answer(locale.t("message.button.invalid"))
        return

    sender_id = f"{sender_prefix}|{callback.from_user.id}"
    result = consume_button(callback.data or "", sender_id)
    if result.status is not ButtonConsumeStatus.SUCCESS:
        await callback.answer(locale.t(_BUTTON_ERROR_KEYS[result.status]))
        return

    await callback.answer()
    if callback.message.reply_markup:
        updated_markup = remove_selected_button(callback.message.reply_markup, callback.data or "")
        try:
            await callback.message.edit_reply_markup(reply_markup=updated_markup)
        except Exception:
            Logger.exception("Failed to remove Telegram button: ")

    target_from = f"{target_prefix}|{callback.message.chat.type.title()}"
    message_id = str(callback.message.message_id)
    session = await SessionInfo.assign(
        target_id=f"{target_from}|{callback.message.chat.id}",
        sender_id=sender_id,
        sender_name=callback.from_user.username,
        target_from=target_from,
        is_private=callback.message.chat.type == "private",
        sender_from=sender_prefix,
        client_name=client_name,
        message_id=message_id,
        reply_id=result.reply_id or message_id,
        messages=MessageChain.assign([Plain(normalize_button_payload(result.payload or ""))]),
        ctx_slot=ctx_slot,
        bot_id=_get_bot_id(),
    )
    await Bot.process_message(session, callback)
