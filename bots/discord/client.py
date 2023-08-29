import discord

intents = discord.Intents.default()
intents.message_content = True
client = discord.Bot(intents=intents)
