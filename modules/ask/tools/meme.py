import asyncio

from modules.meme.moegirl import moegirl
from modules.meme.nbnhhsh import nbnhhsh
from modules.meme.urban import urban
from .utils import locale_en, AkariTool


async def meme(query: str):
    results = await asyncio.gather(
        moegirl(query, locale_en), nbnhhsh(query, locale_en), urban(query, locale_en)
    )
    return f'Moegirlpedia result: {results[0]}\n\nNbnhhsh result: {results[1]}\n\nUrban Dictionary result: {results[2]}'


meme_tool = AkariTool.from_function(
    func=meme,
    description='A tool for looking up Internet memes, powered by Moegirlpedia, Nbnhhsh and Urban Dictionary. Input should be the exact name of the meme.'
)
