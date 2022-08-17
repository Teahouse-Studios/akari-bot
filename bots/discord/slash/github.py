import discord

from bots.discord.client import client
from bots.discord.slash_parser import slash_parser


github = client.create_group("github", "查询Github的相关信息")


@github.command()
@discord.option(name="username_or_repo", description="用户名或仓库名")
async def get(ctx: discord.ApplicationContext, username_or_repo: str):
    await slash_parser(ctx, username_or_repo)


@github.command()
@discord.option(name="keyword", description="搜索关键词")
async def search(ctx: discord.ApplicationContext, keyword: str):
    await slash_parser(ctx, f'search {keyword}')


