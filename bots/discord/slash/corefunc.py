import discord

from bots.discord.client import discord_bot
from bots.discord.slash_parser import slash_parser
from core.config import Config
from core.i18n import get_available_locales


async def auto_get_lang(ctx: discord.AutocompleteContext):
    if not ctx.options["lang"]:
        return get_available_locales()


@discord_bot.slash_command(name="help", description="View details of a module.")
@discord.option(name="module", description="The module you want to know about.")
async def _(ctx: discord.ApplicationContext, module: str):
    await slash_parser(ctx, module)


@discord_bot.slash_command(name="locale", description="Set the bot running languages.")
@discord.option(
    name="lang", description="Supported language codes.", autocomplete=auto_get_lang
)
async def _(ctx: discord.ApplicationContext, lang: str = None):
    if lang:
        await slash_parser(ctx, lang)
    else:
        await slash_parser(ctx, "")


@discord_bot.slash_command(name="mute", description="Make the bot stop sending message.")
async def _(ctx: discord.ApplicationContext):
    await slash_parser(ctx, "")


@discord_bot.slash_command(name="ping", description="Get bot status.")
async def _(ctx: discord.ApplicationContext):
    await slash_parser(ctx, "")


if Config("enable_petal", False):
    @discord_bot.slash_command(name="petal", description="Get the number of petals.")
    async def _(ctx: discord.ApplicationContext):
        await slash_parser(ctx, "")


@discord_bot.slash_command(name="version", description="View bot version.")
async def _(ctx: discord.ApplicationContext):
    await slash_parser(ctx, "")


@discord_bot.slash_command(
    name="whoami",
    description="Get the ID of the user account that sent the command inside the bot.",
)
async def _(ctx: discord.ApplicationContext):
    await slash_parser(ctx, "")


admin = discord_bot.create_group("admin", "Commands available to bot administrators.")


@admin.command(name="add", description="Set members as bot administrators.")
@discord.option(name="userid", description="The user ID.")
async def _(ctx: discord.ApplicationContext, userid: str):
    await slash_parser(ctx, f"add {userid}")


@admin.command(name="remove", description="Remove bot administrator from member.")
@discord.option(name="userid", description="The user ID.")
async def _(ctx: discord.ApplicationContext, userid: str):
    await slash_parser(ctx, f"remove {userid}")


@admin.command(name="list", description="View all bot administrators.")
async def _(ctx: discord.ApplicationContext):
    await slash_parser(ctx, "list")


@admin.command(name="ban", description="Limit someone to use bot in the channel.")
@discord.option(name="userid", description="The user ID.")
async def _(ctx: discord.ApplicationContext, userid: str):
    await slash_parser(ctx, f"ban {userid}")


@admin.command(
    name="unban", description="Remove limit someone to use bot in the channel."
)
@discord.option(name="userid", description="The user ID.")
async def _(ctx: discord.ApplicationContext, userid: str):
    await slash_parser(ctx, f"unban {userid}")


ali = discord_bot.create_group("alias", "Set custom command alias.")


@ali.command(name="add", description="Add custom command alias.")
@discord.option(name="alias", description="The custom alias.")
@discord.option(name="command", description="The command you want to refer to.")
async def _(ctx: discord.ApplicationContext, alias: str, command: str):
    await slash_parser(ctx, f"add {alias} {command}")


@ali.command(name="remove", description="Remove custom command alias.")
@discord.option(name="alias", description="The custom alias.")
async def _(ctx: discord.ApplicationContext, alias: str):
    await slash_parser(ctx, f"remove {alias}")


@ali.command(name="list", description="View custom command alias.")
@discord.option(
    name="legacy", choices=["false", "true"], description="Whether to use legacy mode."
)
async def _(ctx: discord.ApplicationContext, legacy: str):
    legacy = "--legacy" if legacy == "true" else ""
    await slash_parser(ctx, f"list {legacy}")


@ali.command(name="reset", description="Reset custom command alias.")
async def _(ctx: discord.ApplicationContext):
    await slash_parser(ctx, "reset")


m = discord_bot.create_group("module", "Set about modules.")


@m.command(name="list", description="View all available modules.")
@discord.option(
    name="legacy", choices=["false", "true"], description="Whether to use legacy mode."
)
async def _(ctx: discord.ApplicationContext, legacy: str):
    legacy = "--legacy" if legacy == "true" else ""
    await slash_parser(ctx, f"list {legacy}")


p = discord_bot.create_group("prefix", "Set custom command prefix.")


@p.command(name="add", description="Add custom command prefix.")
@discord.option(name="prefix", description="The custom prefix.")
async def _(ctx: discord.ApplicationContext, prefix: str):
    await slash_parser(ctx, f"add {prefix}")


@p.command(name="remove", description="Remove custom command prefix.")
@discord.option(name="prefix", description="The custom prefix.")
async def _(ctx: discord.ApplicationContext, prefix: str):
    await slash_parser(ctx, f"remove {prefix}")


@p.command(name="list", description="View custom command prefix.")
async def _(ctx: discord.ApplicationContext):
    await slash_parser(ctx, "list")


@p.command(name="reset", description="Reset custom command prefix.")
async def _(ctx: discord.ApplicationContext):
    await slash_parser(ctx, "reset")


setup = discord_bot.create_group("setup", "Set up bot actions.")


@setup.command(name="typing", description="Set up whether to display input prompts.")
async def _(ctx: discord.ApplicationContext):
    await slash_parser(ctx, "typing")


@setup.command(name="timeoffset", description="Set the time offset within the session.")
@discord.option(name="offset", description="The timezone offset.")
async def _(ctx: discord.ApplicationContext, offset: str):
    await slash_parser(ctx, f"timeoffset {offset}")


@setup.command(
    name="check", description="Set up whether to enable command typo checking."
)
async def _(ctx: discord.ApplicationContext):
    await slash_parser(ctx, "check")


@setup.command(
    name="cooldown", description="Set up the command cooldown time within the session."
)
@discord.option(name="second", description="The command cooldown seconds.")
async def _(ctx: discord.ApplicationContext, second: str):
    await slash_parser(ctx, f"cooldown {second}")
