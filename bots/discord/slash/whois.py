import discord

from bots.discord.client import client
from bots.discord.slash_parser import slash_parser


@client.slash_command(name="whois", description="Query the information of WHOIS.")
@discord.option(name="domain", description="The domain.")
async def whois(ctx: discord.ApplicationContext, domain: str):
    await slash_parser(ctx, domain)
