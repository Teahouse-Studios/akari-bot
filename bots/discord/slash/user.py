import discord

from bots.discord.client import client
from bots.discord.slash_parser import slash_parser


@client.slash_command(name="user", description="Get information about a MediaWiki user.")
@discord.option(name="username", description="The username, support Interwiki.")
@discord.option(name="enable_profile",
                choices=['false',
                         'true'],
                description="Whether to get extra information about sites using SocialProFile extension.")
async def user(ctx: discord.ApplicationContext, username: str, enable_profile: str):
    p = "-p" if enable_profile == "true" else ""
    await slash_parser(ctx, f"{username} {p}")
