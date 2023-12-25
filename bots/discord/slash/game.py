import discord

from bots.discord.client import client
from bots.discord.slash_parser import slash_parser


@client.slash_command(name="stone", description="Stone Skipping.")
async def stone(ctx: discord.ApplicationContext):
    await slash_parser(ctx, "")


ccode = client.create_group("chemical_code", "A game about chemical formulas.")


@ccode.command(name="default", description="Default mode (Time limits, multiple)")
@discord.option(name="csid", default="", description="Chemspider ID.")
async def default(ctx: discord.ApplicationContext, csid: str):
    await slash_parser(ctx, csid)


@ccode.command(name="captcha", description="Captcha mode (Only once, single)")
async def captcha(ctx: discord.ApplicationContext):
    await slash_parser(ctx, "captcha")


@ccode.command(name="stop", description="Stop the current game.")
async def stop(ctx: discord.ApplicationContext):
    await slash_parser(ctx, "stop")


fish = client.create_group("fish", "Fishing game.")


@fish.command(name="start", description="Throw the fishing rod.")
async def start(ctx: discord.ApplicationContext):
    await slash_parser(ctx, "")


@fish.command(name="retract", description="Retract the fishing rod.")
async def stop(ctx: discord.ApplicationContext):
    await slash_parser(ctx, "retract")


tf = client.create_group("twenty_four", "24 puzzle game.")


@tf.command(name="start", description="Start a new game.")
async def start(ctx: discord.ApplicationContext):
    await slash_parser(ctx, "")


@tf.command(name="stop", description="Stop the current game.")
async def stop(ctx: discord.ApplicationContext):
    await slash_parser(ctx, "stop")


tic_tac_toe = client.create_group("tic_tac_toe", "Play Tic-tac-toe.")


@tic_tac_toe.command(name="random", description="Play with the robot.")
async def random(ctx: discord.ApplicationContext):
    await slash_parser(ctx, "")


@tic_tac_toe.command(name="noob", description="Play with the noob robot.")
async def random(ctx: discord.ApplicationContext):
    await slash_parser(ctx, "noob")


@tic_tac_toe.command(name="expert", description="Play with the expert robot.")
async def random(ctx: discord.ApplicationContext):
    await slash_parser(ctx, "expert")


@tic_tac_toe.command(name="master", description="Play with the master robot.")
async def random(ctx: discord.ApplicationContext):
    await slash_parser(ctx, "master")


@tic_tac_toe.command(name="duo", description="Double player game.")
async def random(ctx: discord.ApplicationContext):
    await slash_parser(ctx, "")


@tic_tac_toe.command(name="stop", description="Stop the current game.")
async def stop(ctx: discord.ApplicationContext):
    await slash_parser(ctx, "stop")