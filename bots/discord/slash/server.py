import discord

from bots.discord.client import client
from bots.discord.slash_parser import slash_parser


async def auto_search(ctx: discord.AutocompleteContext):
    if ctx.options["address"].find(":") == -1:
        return [f'{ctx.options["address"]}:19132', f'{ctx.options["address"]}:25565']
    return [ctx.options["address"]]


@client.slash_command(description="Get Minecraft: Java/Bedrock Edition server motd.")
@discord.option(name="address", description="The server address.", autocomplete=auto_search)
async def server(ctx: discord.ApplicationContext, address: str):
    await slash_parser(ctx, address)
