import discord

from bots.discord.client import client
from bots.discord.slash_parser import slash_parser


@client.slash_command(name="ask", description="Answer your question via ChatGPT.")
@discord.option(name="question", description="Ask ChatGPT.")
async def ask(ctx: discord.ApplicationContext, question: str):
    await slash_parser(ctx, question)
