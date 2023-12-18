import discord

from bots.discord.client import client
from bots.discord.slash_parser import slash_parser


async def auto_complete(ctx: discord.AutocompleteContext):
    if ctx.options["dices"] == '':
        return ['d4', 'd6', 'd8', 'd12', 'd20']


dice = client.create_group("dice", "Random dice.")


@dice.command(description="Roll the specified dice.")
@discord.option(name="dices", autocomplete=auto_complete, description="Dice expression.")
@discord.option(name="dc", default="", description="Difficulty class.")
async def roll(ctx: discord.ApplicationContext, dices: str, dc: str):
    await slash_parser(ctx, f'{dices} {dc}')


@dice.command(description="Modify the checking rule of dc.")
async def rule(ctx: discord.ApplicationContext):
    await slash_parser(ctx, 'rule')
