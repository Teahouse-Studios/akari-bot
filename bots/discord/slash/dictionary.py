import discord

from bots.discord.client import client
from bots.discord.slash_parser import slash_parser


@client.slash_command(description="查询柯林斯词典", name='dict')
@discord.option(name="word", description="词汇")
async def _(ctx: discord.ApplicationContext, word: str):
    await slash_parser(ctx, word)
