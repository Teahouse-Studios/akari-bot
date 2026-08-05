"""Telegram 按钮组件构建。"""

from aiogram.types import CopyTextButton, InlineKeyboardButton, InlineKeyboardMarkup

from core.builtins.message.elements import ActionTextElement
from core.logger import Logger
from core.utils.button_runtime import register_button_rows

TELEGRAM_ACTION_TEXT_MAX_LENGTH = 256
TELEGRAM_ACTION_LABEL_MAX_LENGTH = 64
TELEGRAM_ACTIONS_PER_ROW = 3


def _truncate_label(value: str) -> str:
    if len(value) <= TELEGRAM_ACTION_LABEL_MAX_LENGTH:
        return value
    return value[: TELEGRAM_ACTION_LABEL_MAX_LENGTH - 1] + "…"


def build_telegram_button_markup(
    button_data: list[dict[str, str]],
    allowed_sender_id: str,
    action_texts: list[ActionTextElement] | None = None,
    supports_inline_queries: bool = True,
) -> InlineKeyboardMarkup | None:
    """将普通按钮和 ActionText 转换为 Telegram 内联键盘。"""
    registered_rows = register_button_rows(button_data, allowed_sender_id)
    inline_keyboard = [
        [InlineKeyboardButton(text=button.label, callback_data=button.token) for button in row]
        for row in registered_rows
    ]

    action_buttons = []
    for action_text in action_texts or []:
        text = action_text.text.text
        if not text:
            continue
        if len(text) > TELEGRAM_ACTION_TEXT_MAX_LENGTH:
            Logger.warning(
                f"Telegram ActionText exceeds {TELEGRAM_ACTION_TEXT_MAX_LENGTH} characters and was left as plain text."
            )
            continue
        if supports_inline_queries:
            button = InlineKeyboardButton(
                text=_truncate_label(text),
                switch_inline_query_current_chat=text,
            )
        else:
            button = InlineKeyboardButton(
                text=_truncate_label(text),
                copy_text=CopyTextButton(text=text),
            )
        action_buttons.append(button)

    for start in range(0, len(action_buttons), TELEGRAM_ACTIONS_PER_ROW):
        inline_keyboard.append(action_buttons[start : start + TELEGRAM_ACTIONS_PER_ROW])

    if not inline_keyboard:
        return None
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


def remove_selected_button(markup: InlineKeyboardMarkup, callback_data: str) -> InlineKeyboardMarkup | None:
    """从键盘中只移除指定 callback_data 的按钮。"""
    rows = [[button for button in row if button.callback_data != callback_data] for row in markup.inline_keyboard]
    rows = [row for row in rows if row]
    if not rows:
        return None
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_telegram_context_chat_and_user(ctx) -> tuple:
    """取得 Telegram 消息或回调中的聊天与实际操作用户。"""
    if hasattr(ctx, "message"):
        return ctx.message.chat, ctx.from_user
    return ctx.chat, ctx.from_user
