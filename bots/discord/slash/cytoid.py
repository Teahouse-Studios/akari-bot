import discord

from bots.discord.client import client
from bots.discord.slash_parser import slash_parser


cytoid = client.create_group("cytoid", "查询Cytoid的相关信息")


@cytoid.command(description="查询Best30列表")
async def b30(ctx: discord.ApplicationContext):
    await slash_parser(ctx, "b30")


@cytoid.command(description="查询Recent30列表")
async def r30(ctx: discord.ApplicationContext):
    await slash_parser(ctx, "r30")


@cytoid.command(description="查询个人信息")
async def profile(ctx: discord.ApplicationContext):
    await slash_parser(ctx, "profile")


@cytoid.command(description="绑定用户")
@discord.option(name="username", description="用户名")
async def bind(ctx: discord.ApplicationContext, username: str):
    await slash_parser(ctx, f"bind {username}")


@cytoid.command(description="取消绑定用户")
async def unbind(ctx: discord.ApplicationContext):
    await slash_parser(ctx, "unbind")
