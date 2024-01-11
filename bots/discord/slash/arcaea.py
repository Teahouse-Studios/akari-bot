import discord

from bots.discord.client import client
from bots.discord.slash_parser import slash_parser

arc = client.create_group("arcaea", "Queries about Arcaea.")


@arc.command(name="download", description="Get the latest version of game apk.")
async def download(ctx: discord.ApplicationContext):
    await slash_parser(ctx, "download")


@arc.command(name="random", description="Random a song.")
async def random(ctx: discord.ApplicationContext):
    await slash_parser(ctx, "random")


rank = arcaea.create_subgroup("rank", "View the current daily rank of Arcaea songs.")


@rank.command(name="free", description="View the current rank of the free packs.")
async def free(ctx: discord.ApplicationContext):
    await slash_parser(ctx, "rank free")


@rank.command(name="paid", description="View the current rank of the paid packs.")
async def paid(ctx: discord.ApplicationContext):
    await slash_parser(ctx, "rank paid")
