import discord

from bots.discord.client import client
from bots.discord.slash_parser import slash_parser


async def auto_complete(ctx: discord.AutocompleteContext):
    if not ctx.options["color"]:
        return ['#123456', 'rgb(12,34,56)', 'hsl(123,45%,67%)']


@client.slash_command(description="Get color information.")
@discord.option(name="color", default="", autocomplete=auto_complete,
                description="Color information. Support for Hex, RGB, HSL color code, or name in CSS and Material Design.")
async def color(ctx: discord.ApplicationContext, color: str):
    await slash_parser(ctx, color)
