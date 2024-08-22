import discord

from bots.discord.client import client
from bots.discord.slash_parser import slash_parser


@client.slash_command(name="mcv", description="Get the latest version of Minecraft: Java Edition in the launcher.")
async def mcv(ctx: discord.ApplicationContext):
    await slash_parser(ctx, '')


@client.slash_command(name="mcbv", description="Get the latest version of Minecraft: Bedrock Edition on Mojira.")
async def mcbv(ctx: discord.ApplicationContext):
    await slash_parser(ctx, '')
