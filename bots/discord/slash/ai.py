import discord

from bots.discord.client import client
from bots.discord.slash_parser import slash_parser


@client.slash_command(name="ai", description="Answer your question via LLMs.")
@discord.option(name="question", description="Ask Akaribot.")
async def ask(ctx: discord.ApplicationContext, question: str):
    await slash_parser(ctx, question)
