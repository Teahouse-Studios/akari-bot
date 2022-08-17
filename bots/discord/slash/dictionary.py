import discord

from bots.discord.client import client
from bots.discord.slash_parser import slash_parser


dict_ = client.create_group("dict", "查询柯林斯词典")


@dict_.command(description="查询柯林斯词典")
@discord.option(name="word", description="词汇")
async def query(ctx: discord.ApplicationContext, word: str):
    await slash_parser(ctx, word)
