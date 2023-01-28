import discord

from bots.discord.client import client
from bots.discord.slash_parser import slash_parser


@client.slash_command(description="获取MCBBS新闻")
async def mcbbs_news(ctx: discord.ApplicationContext):
    await slash_parser(ctx, '')
