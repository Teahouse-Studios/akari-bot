import discord

from bots.discord.client import client
from bots.discord.slash_parser import slash_parser


@client.slash_command(description="获取一个Minecraft玩家的信息")
@discord.option(name="player", description="玩家名")
async def mcplayer(ctx: discord.ApplicationContext, player: str):
    await slash_parser(ctx, player)
