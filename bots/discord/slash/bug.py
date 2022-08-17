import discord

from bots.discord.client import client
from bots.discord.slash_parser import slash_parser


async def auto_search(ctx: discord.AutocompleteContext):
    if ctx.options["mojiraid"] == '':
        return ['MC-', 'MCPE-', 'MCD-', 'MCL-', 'REALMS-', 'WEB-', 'MCCE-']


bug = client.create_group("bug", "查询Mojira的相关信息")


@bug.command(description="查询一个已记录在Mojira上的bug信息")
@discord.option(name="mojiraid", autocomplete=auto_search)
async def b30(ctx: discord.ApplicationContext, mojiraid: str):
    await slash_parser(ctx, mojiraid)
