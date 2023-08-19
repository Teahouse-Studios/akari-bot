import discord

from bots.discord.client import client
from bots.discord.slash_parser import slash_parser

tweet = client.create_group("tweet", "获取推文摘要")


@tweet.command()
@discord.option(name="tweetid", description="推文ID")
async def get(ctx: discord.ApplicationContext, tweetid: str):
    await slash_parser(ctx, tweetid)
