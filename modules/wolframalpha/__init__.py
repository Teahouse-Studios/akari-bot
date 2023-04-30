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
    assumption = []
    for pod in res.pods:
        if pod.text is None:
            continue
        assumption.append(pod.text)
    answer = next(res.results).text
    assumptions = ',\n'.join(assumption)
    await msg.finish(f"Answer: {answer}\n===\nAssumption: \n{assumptions}")
