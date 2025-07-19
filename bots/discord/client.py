import discord

from core.config import Config

proxy = Config("proxy", cfg_type=str, secret=True)

intents = discord.Intents.default()
intents.message_content = True
discord_bot = discord.Bot(intents=intents, proxy=proxy)
