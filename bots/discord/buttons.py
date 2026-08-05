"""Discord 按钮组件构建。"""

import secrets
from collections.abc import Awaitable, Callable

import discord

from core.builtins.message.elements import ActionTextElement
from core.logger import Logger
from core.utils.button_runtime import register_button_rows

ButtonClickHandler = Callable[[discord.Interaction, discord.ui.Button], Awaitable[None]]
ActionTextSubmitHandler = Callable[[discord.Interaction, str, bool, discord.Message | None], Awaitable[None]]
_click_handler: ButtonClickHandler | None = None
_action_text_submit_handler: ActionTextSubmitHandler | None = None

ACTION_TEXT_CUSTOM_ID_PREFIX = "aka:"
DISCORD_ACTION_TEXT_MAX_LENGTH = 4000
DISCORD_BUTTON_LABEL_MAX_LENGTH = 80
DISCORD_SELECT_LABEL_MAX_LENGTH = 100


class DiscordButton(discord.ui.Button):
    """将点击委托给适配器入口的按钮。"""

    async def callback(self, interaction: discord.Interaction):
        if _click_handler:
            await _click_handler(interaction, self)


class DiscordButtonView(discord.ui.View):
    """由按钮 token 自行控制有效期的 Discord View。"""

    def __init__(self):
        super().__init__(timeout=None)


def _truncate_label(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 1] + "…"


def _action_label(action_text: ActionTextElement, limit: int = DISCORD_BUTTON_LABEL_MAX_LENGTH) -> str:
    return _truncate_label(action_text.text.text, limit)


class DiscordActionTextModal(discord.ui.Modal):
    """允许用户编辑 ActionText 后再提交的 Discord Modal。"""

    def __init__(
        self,
        action_text: ActionTextElement,
        origin_message: discord.Message | None,
        title: str,
        input_label: str,
    ):
        self.origin_message = origin_message
        self.reference = action_text.reference
        self.command_input = discord.ui.InputText(
            label=_truncate_label(input_label, 45),
            value=action_text.text.text,
            min_length=1,
            max_length=DISCORD_ACTION_TEXT_MAX_LENGTH,
            required=True,
        )
        super().__init__(
            self.command_input,
            title=_truncate_label(title, 45),
            custom_id=f"{ACTION_TEXT_CUSTOM_ID_PREFIX}{secrets.token_urlsafe(9)}",
        )

    async def callback(self, interaction: discord.Interaction):
        if _action_text_submit_handler:
            await _action_text_submit_handler(
                interaction,
                self.command_input.value,
                self.reference,
                self.origin_message,
            )


class DiscordActionTextButton(discord.ui.Button):
    """点击后打开预填命令 Modal 的 ActionText 按钮。"""

    def __init__(
        self,
        action_text: ActionTextElement,
        row: int,
        modal_title: str,
        input_label: str,
    ):
        super().__init__(
            label=_action_label(action_text),
            custom_id=f"{ACTION_TEXT_CUSTOM_ID_PREFIX}{secrets.token_urlsafe(9)}",
            style=discord.ButtonStyle.secondary,
            row=row,
        )
        self.action_text = action_text
        self.modal_title = modal_title
        self.input_label = input_label

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(
            DiscordActionTextModal(
                self.action_text,
                interaction.message,
                self.modal_title,
                self.input_label,
            )
        )


class DiscordActionTextSelect(discord.ui.Select):
    """ActionText 较多时使用下拉菜单节省组件行。"""

    def __init__(
        self,
        action_texts: list[ActionTextElement],
        row: int,
        modal_title: str,
        input_label: str,
        placeholder: str,
    ):
        self.action_texts = action_texts
        self.modal_title = modal_title
        self.input_label = input_label
        super().__init__(
            custom_id=f"{ACTION_TEXT_CUSTOM_ID_PREFIX}{secrets.token_urlsafe(9)}",
            placeholder=_truncate_label(placeholder, 150),
            options=[
                discord.SelectOption(
                    label=_action_label(action_text, DISCORD_SELECT_LABEL_MAX_LENGTH),
                    value=str(index),
                )
                for index, action_text in enumerate(action_texts)
            ],
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        action_text = self.action_texts[int(self.values[0])]
        await interaction.response.send_modal(
            DiscordActionTextModal(
                action_text,
                interaction.message,
                self.modal_title,
                self.input_label,
            )
        )


def set_button_click_handler(handler: ButtonClickHandler) -> None:
    """设置 Discord 按钮点击处理器。"""
    global _click_handler
    _click_handler = handler


def set_action_text_submit_handler(handler: ActionTextSubmitHandler) -> None:
    """设置 Discord ActionText Modal 提交处理器。"""
    global _action_text_submit_handler
    _action_text_submit_handler = handler


def build_discord_button_view(
    button_data: list[dict[str, str]],
    allowed_sender_id: str,
    action_texts: list[ActionTextElement] | None = None,
    modal_title: str = "Edit command",
    input_label: str = "Command",
    select_placeholder: str = "Select a command",
) -> DiscordButtonView | None:
    """将普通按钮和 ActionText 转换为同一个 Discord View。"""
    truncated = len(button_data) > 5 or any(len(row) > 5 for row in button_data[:5])
    rows = [dict(list(row.items())[:5]) for row in button_data[:5]]
    registered_rows = register_button_rows(rows, allowed_sender_id)
    if truncated:
        Logger.warning("Discord button data exceeded platform limits and was truncated.")

    view = DiscordButtonView()
    for row_index, row in enumerate(registered_rows):
        for button in row:
            discord_button = DiscordButton(label=button.label, custom_id=button.token, row=row_index)
            discord_button.disabled = False
            view.add_item(discord_button)

    action_texts = [x for x in (action_texts or []) if 0 < len(x.text.text) <= DISCORD_ACTION_TEXT_MAX_LENGTH]
    available_rows = 5 - len(registered_rows)
    if action_texts and available_rows:
        if len(action_texts) <= 5:
            for index, action_text in enumerate(action_texts):
                row = len(registered_rows) + index // 5
                view.add_item(DiscordActionTextButton(action_text, row, modal_title, input_label))
        else:
            capacity = available_rows * 25
            if len(action_texts) > capacity:
                Logger.warning("Discord ActionText data exceeded platform limits and was truncated.")
            for row_offset, start in enumerate(range(0, min(len(action_texts), capacity), 25)):
                view.add_item(
                    DiscordActionTextSelect(
                        action_texts[start : start + 25],
                        len(registered_rows) + row_offset,
                        modal_title,
                        input_label,
                        select_placeholder,
                    )
                )
    elif action_texts:
        Logger.warning("Discord has no component rows left for ActionText controls.")

    return view if view.children else None


def disable_selected_button(view: discord.ui.View, custom_id: str) -> bool:
    """只停用指定 custom_id 的按钮。"""
    for item in view.children:
        if isinstance(item, discord.ui.Button) and item.custom_id == custom_id:
            item.disabled = True
            return True
    return False
