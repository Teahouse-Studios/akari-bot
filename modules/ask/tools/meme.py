import asyncio

from modules.meme.moegirl import moegirl
from modules.meme.nbnhhsh import nbnhhsh
from modules.meme.urban import urban
from .utils import locale_en, AkariTool


async def meme_all(input: str):
    results = await asyncio.gather(
        moegirl(input, locale_en), nbnhhsh(input, locale_en), urban(input, locale_en)
    )
    return f'Moegirlpedia result: {results[0]}\n\nNbnhhsh result: {results[1]}\n\nUrban Dictionary result: {results[2]}'

meme_tool = AkariTool(
    name='MemeLookup',
    func=meme_all,
    description='A tool for looking up Internet memes, powered by Moegirlpedia, Nbnhhsh and Urban Dictionary. Input should be the exact name of the meme.'
)
