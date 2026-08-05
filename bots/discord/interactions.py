"""Discord 按钮点击回流。"""

import discord
from attrs import define

from bots.discord.buttons import disable_selected_button
from bots.discord.client import discord_bot
from bots.discord.info import client_name, sender_prefix, target_channel_prefix, target_dm_channel_prefix
from core.builtins.bot import Bot
from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import Plain
from core.builtins.session.info import SessionInfo
from core.config.base import BaseConfig
from core.i18n import Locale
from core.logger import Logger
from core.utils.button_runtime import ButtonConsumeStatus, consume_button, normalize_button_payload

_BUTTON_ERROR_KEYS = {
    ButtonConsumeStatus.INVALID: "message.button.invalid",
    ButtonConsumeStatus.EXPIRED: "message.button.expired",
    ButtonConsumeStatus.FORBIDDEN: "message.button.forbidden",
    ButtonConsumeStatus.USED: "message.button.used",
}


@define(frozen=True)
class DiscordActionTextContext:
    """保留 Modal 操作用户，并按需携带原消息引用。"""

    interaction: discord.Interaction
    message: discord.Message | None = None

    @property
    def channel(self):
        return self.interaction.channel

    @property
    def user(self):
        return self.interaction.user


def _get_bot_id() -> str:
    return str(discord_bot.user.id)


async def handle_button_click(
    interaction: discord.Interaction, button: discord.ui.Button, ctx_slot: int | None = None
) -> None:
    """处理 Discord 按钮点击并重新进入消息流程。"""
    sender_id = f"{sender_prefix}|{interaction.user.id}"
    result = consume_button(button.custom_id or "", sender_id)
    if result.status is not ButtonConsumeStatus.SUCCESS:
        key = _BUTTON_ERROR_KEYS[result.status]
        await interaction.response.send_message(Locale(BaseConfig.default_locale).t(key), ephemeral=True)
        return

    if not interaction.response.is_done():
        await interaction.response.defer()

    if button.view and disable_selected_button(button.view, button.custom_id or ""):
        try:
            await interaction.message.edit(view=button.view)
        except Exception:
            Logger.exception("Failed to disable Discord button: ")

    target_from = (
        target_dm_channel_prefix if isinstance(interaction.channel, discord.DMChannel) else target_channel_prefix
    )
    message_id = str(interaction.message.id)
    session = await SessionInfo.assign(
        target_id=f"{target_from}|{interaction.channel.id}",
        sender_id=sender_id,
        sender_name=interaction.user.name,
        target_from=target_from,
        is_private=target_from == target_dm_channel_prefix,
        sender_from=sender_prefix,
        client_name=client_name,
        message_id=message_id,
        reply_id=result.reply_id or message_id,
        messages=MessageChain.assign([Plain(normalize_button_payload(result.payload or ""))]),
        ctx_slot=ctx_slot,
        bot_id=_get_bot_id(),
    )
    await Bot.process_message(session, interaction)


async def handle_action_text_submit(
    interaction: discord.Interaction,
    command: str,
    reference: bool,
    origin_message: discord.Message | None,
    ctx_slot: int | None = None,
) -> None:
    """将 Discord Modal 中编辑后的命令作为用户输入重新进入消息流程。"""
    if not interaction.response.is_done():
        await interaction.response.defer()

    target_from = (
        target_dm_channel_prefix if isinstance(interaction.channel, discord.DMChannel) else target_channel_prefix
    )
    origin_message_id = str(origin_message.id) if origin_message else None
    session = await SessionInfo.assign(
        target_id=f"{target_from}|{interaction.channel.id}",
        sender_id=f"{sender_prefix}|{interaction.user.id}",
        sender_name=interaction.user.name,
        target_from=target_from,
        is_private=target_from == target_dm_channel_prefix,
        sender_from=sender_prefix,
        client_name=client_name,
        message_id=str(interaction.id),
        reply_id=origin_message_id if reference else None,
        messages=MessageChain.assign([Plain(command)]),
        ctx_slot=ctx_slot,
        bot_id=_get_bot_id(),
    )
    await Bot.process_message(
        session,
        DiscordActionTextContext(interaction, origin_message if reference else None),
    )
