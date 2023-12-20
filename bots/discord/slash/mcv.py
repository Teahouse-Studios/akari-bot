import discord

from bots.discord.client import client
from bots.discord.slash_parser import slash_parser


@client.slash_command(name="mcv", description="Get the latest version of Minecraft: Java Edition in the launcher.")
async def mcv(ctx: discord.ApplicationContext):
    await slash_parser(ctx, '')


@client.slash_command(name="mcbv", description="Get the latest version of Minecraft: Bedrock Edition on Mojira.")
async def mcbv(ctx: discord.ApplicationContext):
    await slash_parser(ctx, '')


@client.slash_command(name="mcdv", description="Get the latest version of Minecraft Dungeons on Mojira.")
async def mcdv(ctx: discord.ApplicationContext):
    await slash_parser(ctx, '')


@client.slash_command(name="mcev", description="Get the latest version of Minecraft: Education Edition in Windows Edition.")
async def mcev(ctx: discord.ApplicationContext):
    await slash_parser(ctx, '')


@client.slash_command(name="mclgv", description="Get the latest version of Minecraft Legends on Mojira.")
async def mclgv(ctx: discord.ApplicationContext):
    await slash_parser(ctx, '')