import discord

from core.config import config

intents = discord.Intents.default()
intents.message_content = True
client = discord.Bot(intents=intents, proxy=config('proxy', cfg_type=str, secret=True))
