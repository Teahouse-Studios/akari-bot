import discord

from bots.discord.client import client
from bots.discord.slash_parser import slash_parser


@client.slash_command(description="获取Minecraft Java版的最新版本信息")
async def mcv(ctx: discord.ApplicationContext):
    await slash_parser(ctx, '')


@client.slash_command(description="获取Minecraft基岩版的最新版本信息")
async def mcbv(ctx: discord.ApplicationContext):
    await slash_parser(ctx, '')


@client.slash_command(description="获取Minecraft Dungeons的最新版本信息")
async def mcdv(ctx: discord.ApplicationContext):
    await slash_parser(ctx, '')


@client.slash_command(description="获取Minecraft教育版的最新版本信息")
async def mcev(ctx: discord.ApplicationContext):
    await slash_parser(ctx, '')
