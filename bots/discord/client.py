import discord

from core.config.base import CoreSecretConfig

proxy = CoreSecretConfig.proxy

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
discord_bot = discord.Bot(intents=intents, proxy=proxy)
