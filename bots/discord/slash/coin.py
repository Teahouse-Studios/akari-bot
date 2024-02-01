import discord

from bots.discord.client import client
from bots.discord.slash_parser import slash_parser


@client.slash_command(name="coin", description="Toss coin.")
@discord.option(name="amount", description="Toss any number of coins.")
async def coin(ctx: discord.ApplicationContext, amount: int = 1):
    await slash_parser(ctx, amount)
