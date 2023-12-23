import colorsys
import discord
import random

from bots.discord.client import client
from bots.discord.slash_parser import slash_parser


async def auto_complete(ctx: discord.AutocompleteContext):
    color_code = "#{:06x}".format(random.randint(0, 0xFFFFFF))
    rgb = tuple(int(color_code[i:i+2], 16) for i in (1, 3, 5))
    hsl = colorsys.rgb_to_hls(rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0)

    if not ctx.options["color"]:
        return [color_code, 
            f'rgb({",".join(map(str, rgb))})',
            f'hsl({','.join(map(str, (int(hsl[0] * 360), int(hsl[1] * 100), int(hsl[2] * 100))))})']


@client.slash_command(name="color", description="Get color information.")
@discord.option(name="color", default="", autocomplete=auto_complete,
                description="Color information. Support for Hex, RGB, HSL color code, or name in CSS and Material Design.")
async def color(ctx: discord.ApplicationContext, color: str):
    await slash_parser(ctx, color)
