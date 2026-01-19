import discord

from bots.discord.client import discord_bot
from bots.discord.slash_parser import slash_parser


async def auto_search(ctx: discord.AutocompleteContext):
    if not ctx.options["mojiraid"]:
        return ["BDS-", "MCPE-", "MCD-", "MCL-", "MCLG-", "REALMS-", "MC-", "WEB-"]


@discord_bot.command(
    name="bugtracker", description="Query the corresponding ticket on Mojira."
)
@discord.option(
    name="mojiraid", autocomplete=auto_search, description="Mojira ticket ID."
)
async def _(ctx: discord.ApplicationContext, mojiraid: str):
    await slash_parser(ctx, mojiraid)
