import discord

from bots.discord.client import discord_bot
from bots.discord.slash_parser import slash_parser


@discord_bot.slash_command(description="梗查询")
@discord.option(name="keywords", description="关键词")
async def meme(ctx: discord.ApplicationContext, keywords: str):
    await slash_parser(ctx, keywords)
