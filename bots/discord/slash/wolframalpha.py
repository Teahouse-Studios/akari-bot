import discord

from bots.discord.client import client
from bots.discord.slash_parser import slash_parser


wolframalpha = client.create_group("wolframalpha", "Use WolframAlpha.")

@wolframalpha.command(name="query", description="Input a question or formula to search for WolframAlpha.")
@discord.option(name="query", description="Enter what you want to calculate.")
async def query(ctx: discord.ApplicationContext, query: str):
    await slash_parser(ctx, query)


@wolframalpha.command(name="ask", description="Answer the question via WolframAlpha.")
@discord.option(name="question", description="Ask WolframAlpha.")
async def ask(ctx: discord.ApplicationContext, question: str):
    await slash_parser(ctx, f"ask {question}")