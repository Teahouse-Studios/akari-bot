import discord

from bots.discord.client import client
from bots.discord.slash_parser import slash_parser

mai = client.create_group("maimai", "Queries about Maimai DX.")


@mai.command(name="b50", description="Query the Best50 list.")
@discord.option(name="beta", choices=['false', 'true'], description="Whether to use Beta mode.")
@discord.option(name="username", description="Your MaimaiDX-prober username.")
async def b50(ctx: discord.ApplicationContext, beta: str, username: str = None):
    beta = "beta " if beta == "true" else ""
    await slash_parser(ctx, f"b50 {beta}{username}")


@mai.command(name="bind", description="Bind user.")
@discord.option(name="username", description="Your MaimaiDX-prober username.")
async def bind(ctx: discord.ApplicationContext, username: str):
    await slash_parser(ctx, f"bind {username}")


@mai.command(name="unbind", description="Unbind user.")
async def unbind(ctx: discord.ApplicationContext):
    await slash_parser(ctx, "unbind")


chu = client.create_group("chunithm", "Queries about CHUNITHM.")


@chu.command(name="b30", description="Query the Best30 list.")
@discord.option(name="username", description="Your MaimaiDX-prober username.")
async def b50(ctx: discord.ApplicationContext, username: str = None):
    await slash_parser(ctx, f"b30 {username}")


@chu.command(name="bind", description="Bind user.")
@discord.option(name="username", description="Your MaimaiDX-prober username.")
async def bind(ctx: discord.ApplicationContext, username: str):
    await slash_parser(ctx, f"bind {username}")


@chu.command(name="unbind", description="Unbind user.")
async def unbind(ctx: discord.ApplicationContext):
    await slash_parser(ctx, "unbind")