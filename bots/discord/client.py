import discord

from config import Config

intents = discord.Intents.default()
intents.message_content = True
client = discord.Bot(intents=intents, proxy=Config('proxy'))
