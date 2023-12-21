import discord

from bots.discord.client import client
from bots.discord.slash_parser import slash_parser

@client.slash_command(name="tweet", description="Get tweet image from tweet ID or link.")
@discord.option(name="tweetid", description="The tweet ID or tweet link.")
async def tweet(ctx: discord.ApplicationContext, tweetid: str):
    await slash_parser(ctx, tweet)
