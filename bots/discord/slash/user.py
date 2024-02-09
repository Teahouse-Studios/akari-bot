import discord

from bots.discord.client import client
from bots.discord.slash_parser import slash_parser


@client.slash_command(name="user", description="Get information about a MediaWiki user.")
@discord.option(name="username", description="The username, support Interwiki.")
@discord.option(name="gamepedia_mode", choices=['false', 'true'], description="Whether to get extra information from Gamepedia site.")
async def user(ctx: discord.ApplicationContext, username: str, gamepedia_mode: str):
    extra = "-r" if gamepedia_mode == "true" else ""
    await slash_parser(ctx, f"{username} {extra}")
