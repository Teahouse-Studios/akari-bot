import discord

from bots.discord.client import client
from bots.discord.slash_parser import slash_parser

@client.slash_command(description="Convert currency prices according to the exchange rate of the day.")
@discord.option(name="amount", default=1.0, description="The amount of base currency.")
@discord.option(name="base", description="The base currency unit.")
@discord.option(name="target", description="The target currency unit.")
async def exchange_rate(ctx: discord.ApplicationContext, amount: float, base: str, target: str):
    await slash_parser(ctx, f"{amount}{base} {target}")