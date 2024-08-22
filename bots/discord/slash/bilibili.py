import discord

from bots.discord.client import client
from bots.discord.slash_parser import slash_parser


@client.slash_command(name="bilibili", description="Send video ID for video info.")
@discord.option(name="bid", description="Bilibili video ID.")
async def bilibili(ctx: discord.ApplicationContext, bid: str):
    await slash_parser(ctx, bid)
