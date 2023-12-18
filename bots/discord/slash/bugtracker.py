import discord

from bots.discord.client import client
from bots.discord.slash_parser import slash_parser


async def auto_search(ctx: discord.AutocompleteContext):
    if ctx.options["mojiraid"] == '':
        return ['BDS-', 'MCPE-', 'MCD-', 'MCL-', 'MCLG-', 'REALMS-', 'MC-', 'WEB-']

@client.command(description="Query the corresponding ticket on Mojira.")
@discord.option(name="mojiraid", autocomplete=auto_search)
async def bugtracker(ctx: discord.ApplicationContext, mojiraid: str):
    await slash_parser(ctx, mojiraid)
