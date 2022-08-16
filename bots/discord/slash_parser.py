import asyncio

import discord

from bots.discord.slash_message import MessageSession
from core.elements import MsgInfo, Session
from core.logger import Logger
from core.parser.message import parser


async def slash_parser(ctx: discord.ApplicationContext, command: str):
    await ctx.defer()
    target = "Discord|Channel"
    if isinstance(ctx.channel, discord.DMChannel):
        target = "Discord|DM|Channel"
    targetId = f"{target}|{ctx.channel.id}"
    session = MessageSession(target=MsgInfo(targetId=targetId,
                                            senderId=f"Discord|Client|{ctx.author.id}",
                                            senderName=ctx.author.name, targetFrom=target, senderFrom="Discord|Client",
                                            clientName='Discord|Slash',
                                            messageId=0),
                             session=Session(message=ctx, target=ctx.channel, sender=ctx.author))
    session.command = f'/{str(ctx.command).split(" ")[0]} {command}'
    Logger.info(f'parsing..')
    await parser(session, prefix=['/'])
