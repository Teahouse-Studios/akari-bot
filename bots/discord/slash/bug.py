import discord

from bots.discord.client import client
from bots.discord.slash_parser import slash_parser


async def auto_search(ctx: discord.AutocompleteContext):
    if ctx.options["mojiraid"] == '':
        return ['MC-', 'MCPE-', 'MCD-', 'MCL-', 'REALMS-', 'WEB-', 'MCCE-']


@client.command(description="查询一个已记录在Mojira上的bug信息")
@discord.option(name="mojiraid", autocomplete=auto_search)
async def bug(ctx: discord.ApplicationContext, mojiraid: str):
    await slash_parser(ctx, mojiraid)
