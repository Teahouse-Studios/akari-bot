import discord

from bots.discord.client import client
from bots.discord.slash_parser import slash_parser


async def example_question(ctx: discord.AutocompleteContext):
    if ctx.options["question"] == "":
      question = ["Who are you?", 
                  "What does AI work?",
                  "How to maintain a healthy lifestyle?",
                  "Teach me how to bake a cake.",
                  "What is the answer to the ultimate question of life, The universe, and everything?"]
        return question


@client.slash_command(description="Answer your question via ChatGPT.")
@discord.option(name="question", description="Ask ChatGPT...", autocomplete=example_question)
async def ask(ctx: discord.ApplicationContext, question: str):
    await slash_parser(ctx, question)
