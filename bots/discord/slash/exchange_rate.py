import discord

from bots.discord.client import client
from bots.discord.slash_parser import slash_parser

@client.slash_command(name="exchange_rate", description="Convert currency prices according to the exchange rate of the day.")
@discord.option(name="base", description="The base currency unit.")
@discord.option(name="target", description="The target currency unit.")
@discord.option(name="amount", description="The amount of base currency.")
async def excr(ctx: discord.ApplicationContext, base: str, target: str, amount: float=1.0):
    await slash_parser(ctx, f"{amount}{base} {target}")
