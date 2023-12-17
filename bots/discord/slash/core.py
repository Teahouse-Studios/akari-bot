import discord

from bots.discord.client import client
from bots.discord.slash_parser import slash_parser
from core.utils.i18n import get_available_locales

@client.slash_command(description="Set the bot running languages.")
@discord.option(name="lang", description="Supported language codes.")
async def locale(ctx: discord.ApplicationContext):
    await slash_parser(ctx, lang)


@client.slash_command(description="Make the bot stop sending message.")
async def mute(ctx: discord.ApplicationContext):
    await slash_parser(ctx, '')


@client.slash_command(description="Get bot status.")
async def ping(ctx: discord.ApplicationContext):
    await slash_parser(ctx, '')


@client.slash_command(description="View bot version.")
async def version(ctx: discord.ApplicationContext):
    await slash_parser(ctx, '')


@client.slash_command(description="Get the ID of the user account that sent the command inside the bot.")
async def whoami(ctx: discord.ApplicationContext):
    await slash_parser(ctx, '')


admin = client.create_group("admin", "Commands available to bot administrators.")


@admin.slash_command(description="Set members as bot administrators.")
@discord.option(name="user_id", description="The user ID.")
async def add(ctx: discord.ApplicationContext):
    await slash_parser(ctx, f'add {user_id}')


@admin.slash_command(description="Remove bot administrator from member.")
@discord.option(name="user_id", description="The user ID.")
async def remove(ctx: discord.ApplicationContext):
    await slash_parser(ctx, f'remove {user_id}')


@admin.slash_command(description="View all bot administrators.")
async def show(ctx: discord.ApplicationContext):
    await slash_parser(ctx, f'list')


@admin.slash_command(description="Limit someone to use bot in the channel.")
@discord.option(name="user_id", description="The user ID.")
async def ban(ctx: discord.ApplicationContext):
    await slash_parser(ctx, f'ban {user_id}')


@admin.slash_command(description="Remove limit someone to use bot in the channel.")
@discord.option(name="user_id", description="The user ID.")
async def ban(ctx: discord.ApplicationContext):
    await slash_parser(ctx, f'unban {user_id}')
