import discord

from bots.discord.client import client
from bots.discord.slash_parser import slash_parser

arcaea = client.create_group("arcaea", "Queries about Arcaea.")


@arcaea.command(description="Get the latest version of game apk.")
async def download(ctx: discord.ApplicationContext):
    await slash_parser(ctx, "download")


@arcaea.command(description="Random a song.")
async def random(ctx: discord.ApplicationContext):
    await slash_parser(ctx, "random")


rank = arcaea.create_subgroup("rank", "View the current daily rank of Arcaea songs.")


@rank.command(description="View the current rank of the free packs.")
async def free(ctx: discord.ApplicationContext):
    await slash_parser(ctx, "rank free")


@rank.command(description="View the current rank of the paid packs.")
async def paid(ctx: discord.ApplicationContext):
    await slash_parser(ctx, "rank paid")
