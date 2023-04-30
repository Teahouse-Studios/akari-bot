import wolframalpha
import asyncio

from core.builtins import Bot
from core.component import module
from config import Config

client = wolframalpha.Client(Config('wolfram_alpha_appid'))

w = module(
    'wolframalpha',
    alias={
        'wolfram': 'wolframalpha'},
    developers=['Dianliang233'],
    desc='{wolframalpha.help.desc}',
    support_languages=['en'])


@w.handle('<query> {{wolframalpha.help.query}}')
async def _(msg: Bot.MessageSession):
    query = msg.parsed_msg['<query>']
    res = await asyncio.get_event_loop().run_in_executor(None, client.query, query)
    details = res.details
    answer = []
    for title, detail in details.items():
        answer.append(f'{title}: {detail}')
    await msg.finish('\n'.join(answer))
