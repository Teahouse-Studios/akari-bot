import discord

from bots.discord.client import client
from bots.discord.slash_parser import slash_parser

tweet = client.create_group("tweet", "Get tweet image from tweet ID or link.")


@tweet.command()
@discord.option(name="tweet", description="The tweet ID or tweet link.")
async def get(ctx: discord.ApplicationContext, tweet: str):
    await slash_parser(ctx, tweet)
