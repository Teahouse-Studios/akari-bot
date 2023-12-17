import discord

from bots.discord.client import client
from bots.discord.slash_parser import slash_parser


@client.slash_command(description="Get Minecraft player information.")
@discord.option(name="username_or_uuid", description="The name or UUID of Minecraft player.")
async def mcplayer(ctx: discord.ApplicationContext, username_or_uuid: str):
    await slash_parser(ctx, username_or_uuid)
