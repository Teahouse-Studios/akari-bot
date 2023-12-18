import discord

from bots.discord.client import client
from bots.discord.slash_parser import slash_parser

cytoid = client.create_group("cytoid", "Query about Cytoid.")


@cytoid.command(description="Query the Best 30 list.")
async def b30(ctx: discord.ApplicationContext):
    await slash_parser(ctx, "b30")


@cytoid.command(description="Query the Recent 30 list.")
async def r30(ctx: discord.ApplicationContext):
    await slash_parser(ctx, "r30")


@cytoid.command(description="Query user profile.")
async def profile(ctx: discord.ApplicationContext):
    await slash_parser(ctx, "profile")


@cytoid.command(description="Bind user.")
@discord.option(name="username", description="Your Cytoid username.")
async def bind(ctx: discord.ApplicationContext, username: str):
    await slash_parser(ctx, f"bind {username}")


@cytoid.command(description="Unbind user.")
async def unbind(ctx: discord.ApplicationContext):
    await slash_parser(ctx, "unbind")
