"""Telegram 按钮组件构建。"""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from core.utils.button_runtime import register_button_rows


def build_telegram_button_markup(
    button_data: list[dict[str, str]], allowed_sender_id: str
) -> InlineKeyboardMarkup | None:
    """将通用按钮数据转换为 Telegram 内联键盘。"""
    registered_rows = register_button_rows(button_data, allowed_sender_id)
    if not registered_rows:
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=button.label, callback_data=button.token) for button in row]
            for row in registered_rows
        ]
    )


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
