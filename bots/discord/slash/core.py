import discord

from bots.discord.client import client
from bots.discord.slash_parser import slash_parser
from core.utils.i18n import get_available_locales


@client.slash_command(description="Set the bot running languages.")
@discord.option(name="lang", default="", description="Supported language codes.")
async def locale(ctx: discord.ApplicationContext, lang: str):
    await slash_parser(ctx, lang)


@client.slash_command(description="Make the bot stop sending message.")
async def mute(ctx: discord.ApplicationContext):
    await slash_parser(ctx, "")


@client.slash_command(description="Get bot status.")
async def ping(ctx: discord.ApplicationContext):
    await slash_parser(ctx, "")


@client.slash_command(description="View bot version.")
async def version(ctx: discord.ApplicationContext):
    await slash_parser(ctx, "")


@client.slash_command(description="Get the ID of the user account that sent the command inside the bot.")
async def whoami(ctx: discord.ApplicationContext):
    await slash_parser(ctx, "")


admin = client.create_group("admin", "Commands available to bot administrators.")


@admin.command(description="Set members as bot administrators.")
@discord.option(name="userid", description="The user ID.")
async def add(ctx: discord.ApplicationContext, userid: str):
    await slash_parser(ctx, f"add {userid}")


@admin.command(description="Remove bot administrator from member.")
@discord.option(name="userid", description="The user ID.")
async def remove(ctx: discord.ApplicationContext, userid: str):
    await slash_parser(ctx, f"remove {userid}")


@admin.command(description="View all bot administrators.")
async def list(ctx: discord.ApplicationContext):
    await slash_parser(ctx, "list")


@admin.command(description="Limit someone to use bot in the channel.")
@discord.option(name="userid", description="The user ID.")
async def ban(ctx: discord.ApplicationContext, userid: str):
    await slash_parser(ctx, f"ban {userid}")


@admin.command(description="Remove limit someone to use bot in the channel.")
@discord.option(name="userid", description="The user ID.")
async def unban(ctx: discord.ApplicationContext, userid: str):
    await slash_parser(ctx, f"unban {userid}")
    

setup = client.create_group("setup", "Set up bot actions.")


@setup.command(description="Set up whether to display input prompts.")
async def typing(ctx: discord.ApplicationContext):
    await slash_parser(ctx, "typing")


@setup.command(description="Set the time offset.")
@discord.option(name="offset", description="The timezone offset.")
async def offset(ctx: discord.ApplicationContext, offset: str):
    await slash_parser(ctx, f"timeoffset {offset}")