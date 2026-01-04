import discord

from bots.discord.info import *
from bots.discord.slash_context import DiscordSlashContextManager
from core.builtins.bot import Bot
from core.builtins.message.chain import MessageChain
from core.builtins.session.info import SessionInfo
from core.logger import Logger

slash_ctx_id = Bot.register_context_manager(DiscordSlashContextManager)


async def ctx_to_session(ctx: discord.ApplicationContext | discord.AutocompleteContext,
                         command: str) -> SessionInfo:
    target_from = target_channel_prefix
    if isinstance(ctx, discord.ApplicationContext):
        if isinstance(ctx.channel, discord.DMChannel):
            target_from = target_dm_channel_prefix
        target_id = f"{target_from}|{ctx.channel.id}"
        sender_id = f"{sender_prefix}|{ctx.author.id}"
    else:
        if isinstance(ctx.interaction.channel, discord.PartialMessage):
            target_id = f"{target_dm_channel_prefix}|{ctx.interaction.channel.id}"
        else:
            target_id = f"{target_from}|{ctx.interaction.channel_id}"
        sender_id = f"{sender_prefix}|{ctx.interaction.user.id}"
    msg_chain = MessageChain.assign(f"/{str(ctx.command).split(" ")[0]} {command}")

    session = await SessionInfo.assign(target_id=target_id, sender_id=sender_id, sender_name=(
        ctx.author.name
        if isinstance(ctx, discord.ApplicationContext)
        else ctx.interaction.user.name
    ),
        target_from=target_from, sender_from=sender_prefix, client_name=client_name,
        message_id=str(ctx.command.id), messages=msg_chain, ctx_slot=slash_ctx_id,
        prefixes=["~", "/"],
        require_enable_modules=False)

    return session


async def slash_parser(ctx: discord.ApplicationContext, command: str):
    session = await ctx_to_session(ctx, command)
    Logger.info("Parsing...")
    await Bot.process_message(session, ctx)
