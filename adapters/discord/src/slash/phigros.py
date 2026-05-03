import discord

from bots.discord.client import discord_bot
from bots.discord.slash_parser import slash_parser

phigros = discord_bot.create_group("phigros", "查询Phigros的相关信息")


@phigros.command(description="查询Best19列表")
async def _(ctx: discord.ApplicationContext):
    await slash_parser(ctx, "b19")


@phigros.command(description="绑定用户")
@discord.option(name="sessiontoken", description="用户令牌")
async def _(ctx: discord.ApplicationContext, sessiontoken: str):
    await slash_parser(ctx, f"bind {sessiontoken}")


@phigros.command(description="取消绑定用户")
async def _(ctx: discord.ApplicationContext):
    await slash_parser(ctx, "unbind")
