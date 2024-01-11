import colorsys
import discord
import random

from bots.discord.client import client
from bots.discord.slash_parser import slash_parser


@client.slash_command(name="color", description="Get color information.")
@discord.option(name="color",
                description="Color information. Support for Hex, RGB, HSL color code, or name in CSS and Material Design.")
async def color(ctx: discord.ApplicationContext, color: str=None):
    if color:
        await slash_parser(ctx, color)
    else:
        await slash_parser(ctx, "")
