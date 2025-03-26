from typing import Union

import discord

from bots.discord.info import *
from bots.discord.slash_message import MessageSession
from core.logger import Logger
from core.parser.message import parser
from core.types import MsgInfo, Session


def ctx_to_session(ctx: Union[discord.ApplicationContext, discord.AutocompleteContext]):
    target = target_channel_prefix
    if isinstance(ctx, discord.ApplicationContext):
        if isinstance(ctx.channel, discord.DMChannel):
            target = target_dm_channel_prefix
        target_id = f"{target}|{ctx.channel.id}"
        sender_id = f"{sender_prefix}|{ctx.author.id}"
    else:
        if isinstance(ctx.interaction.channel, discord.PartialMessage):
            target_id = f"{target_dm_channel_prefix}|{ctx.interaction.channel.id}"
        else:
            target_id = f"{target}|{ctx.interaction.channel_id}"
        sender_id = f"{sender_prefix}|{ctx.interaction.user.id}"
    return MessageSession(
        target=MsgInfo(
            target_id=target_id,
            sender_id=sender_id,
            sender_name=(
                ctx.author.name
                if isinstance(ctx, discord.ApplicationContext)
                else ctx.interaction.user.name
            ),
            target_from=target_slash_prefix,
            sender_from=sender_prefix,
            client_name=target_slash_prefix,
            message_id=0,
        ),
        session=Session(
            message=ctx,
            target=(
                ctx.channel
                if isinstance(ctx, discord.ApplicationContext)
                else ctx.interaction.channel
            ),
            sender=(
                ctx.author
                if isinstance(ctx, discord.ApplicationContext)
                else ctx.interaction.user
            ),
        ),
    )


async def slash_parser(ctx: discord.ApplicationContext, command: str):
    await ctx.defer()
    session = ctx_to_session(ctx)
    session.command = f"/{str(ctx.command).split(" ")[0]} {command}"
    Logger.info("Parsing...")
    await parser(session, prefix=["~", "/"], require_enable_modules=False)
