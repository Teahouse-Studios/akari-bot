"""Discord 按钮组件构建。"""

from collections.abc import Awaitable, Callable

import discord

from core.logger import Logger
from core.utils.button_runtime import register_button_rows

ButtonClickHandler = Callable[[discord.Interaction, discord.ui.Button], Awaitable[None]]
_click_handler: ButtonClickHandler | None = None


class DiscordButton(discord.ui.Button):
    """将点击委托给适配器入口的按钮。"""

    async def callback(self, interaction: discord.Interaction):
        if _click_handler:
            await _click_handler(interaction, self)


class DiscordButtonView(discord.ui.View):
    """由按钮 token 自行控制有效期的 Discord View。"""

    def __init__(self):
        super().__init__(timeout=None)


def set_button_click_handler(handler: ButtonClickHandler) -> None:
    """设置 Discord 按钮点击处理器。"""
    global _click_handler
    _click_handler = handler


def build_discord_button_view(button_data: list[dict[str, str]], allowed_sender_id: str) -> DiscordButtonView | None:
    """将通用按钮数据转换为 Discord View。"""
    truncated = len(button_data) > 5 or any(len(row) > 5 for row in button_data[:5])
    rows = [dict(list(row.items())[:5]) for row in button_data[:5]]
    registered_rows = register_button_rows(rows, allowed_sender_id)
    if not registered_rows:
        return None
    if truncated:
        Logger.warning("Discord button data exceeded platform limits and was truncated.")

    view = DiscordButtonView()
    for row_index, row in enumerate(registered_rows):
        for button in row:
            discord_button = DiscordButton(label=button.label, custom_id=button.token, row=row_index)
            discord_button.disabled = False
            view.add_item(discord_button)
    return view


def disable_selected_button(view: discord.ui.View, custom_id: str) -> bool:
    """只停用指定 custom_id 的按钮。"""
    for item in view.children:
        if isinstance(item, discord.ui.Button) and item.custom_id == custom_id:
            item.disabled = True
            return True
    return False
