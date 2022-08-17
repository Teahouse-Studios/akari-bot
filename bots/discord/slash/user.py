import discord

from bots.discord.client import client
from bots.discord.slash_parser import slash_parser, ctx_to_session


@client.slash_command(description="查询一个已记录在Mediawiki上的用户信息")
@discord.option(name="username", description="用户名")
async def user(ctx: discord.ApplicationContext, username: str):
    await slash_parser(ctx, username)
