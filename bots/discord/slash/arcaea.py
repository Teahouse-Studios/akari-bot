import re

import discord

from bots.discord.client import client
from bots.discord.slash_parser import slash_parser, ctx_to_session


arcaea = client.create_group("arcaea", "查询arcaea的相关信息", guild_ids=[557879624575614986])


@arcaea.command(description="查询best30列表")
async def b30(ctx: discord.ApplicationContext):
    await slash_parser(ctx, "b30")


@arcaea.command(description="查询最近游玩记录")
async def info(ctx: discord.ApplicationContext):
    await slash_parser(ctx, "info")


@arcaea.command(description="绑定账户")
@discord.option(name="friendcode", description="好友代码")
async def bind(ctx: discord.ApplicationContext, friendcode: str):
    await slash_parser(ctx, f"bind {friendcode}")


@arcaea.command(description="取消绑定账户")
async def unbind(ctx: discord.ApplicationContext):
    await slash_parser(ctx, "unbind")


@arcaea.command(description="获取最新版本的arcaea安卓版链接")
async def download(ctx: discord.ApplicationContext):
    await slash_parser(ctx, "download")


@arcaea.command(description="随机一首歌曲")
async def random(ctx: discord.ApplicationContext):
    await slash_parser(ctx, "random")


rank = arcaea.subgroup("rank", "查询arcaea日排行榜的相关信息")


@rank.command(description="查询arcaea免费包当前日排行榜")
async def free(ctx: discord.ApplicationContext):
    await slash_parser(ctx, "free")


@rank.command(description="查询arcaea收费包当前日排行榜")
async def paid(ctx: discord.ApplicationContext):
    await slash_parser(ctx, "paid")
