import discord

from bots.discord.client import client
from bots.discord.slash_parser import slash_parser


github = client.create_group("github", "Github query tool.")


@github.command(name="get", description="Trying to automatically identifying and distinguishing repo/user.")
@discord.option(name="name", description="GitHub user or repository name.")
async def get(ctx: discord.ApplicationContext, name: str):
    await slash_parser(ctx, name)


@github.command(name="repo", description="Get GitHub repository information.")
@discord.option(name="name", description="GitHub repository name.")
async def repo(ctx: discord.ApplicationContext, name: str):
    await slash_parser(ctx, f'repo {name}')


@github.command(name="user", description="Get GitHub user or organization information.")
@discord.option(name="name", description="GitHub user name.")
async def user(ctx: discord.ApplicationContext, name: str):
    await slash_parser(ctx, f'user {name}')


@github.command(name="search", description="Search repositories on GitHub.")
@discord.option(name="query", description="Search keywords.")
async def search(ctx: discord.ApplicationContext, query: str):
    await slash_parser(ctx, f'search {keyword}')
