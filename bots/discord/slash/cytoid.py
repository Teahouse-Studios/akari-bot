import discord

from bots.discord.client import discord_bot
from bots.discord.slash_parser import slash_parser

ctd = discord_bot.create_group("cytoid", "Query about Cytoid.")


@ctd.command(name="b30", description="Query the Best30 list.")
async def _(ctx: discord.ApplicationContext):
    await slash_parser(ctx, "b30")


@ctd.command(name="r30", description="Query the Recent30 list.")
async def _(ctx: discord.ApplicationContext):
    await slash_parser(ctx, "r30")


@ctd.command(name="profile", description="Query user profile.")
async def _(ctx: discord.ApplicationContext):
    await slash_parser(ctx, "profile")


@ctd.command(name="bind", description="Bind user.")
@discord.option(name="username", description="Your Cytoid username.")
async def _(ctx: discord.ApplicationContext, username: str):
    await slash_parser(ctx, f"bind {username}")


@ctd.command(name="unbind", description="Unbind user.")
async def _(ctx: discord.ApplicationContext):
    await slash_parser(ctx, "unbind")
