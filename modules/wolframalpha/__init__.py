import asyncio

import wolframalpha

from config import Config
from core.builtins import Bot, Image
from core.component import module
from core.dirty_check import check_bool

client = wolframalpha.Client(Config('wolfram_alpha_appid'))

w = module(
    'wolframalpha',
    alias='wolfram',
    developers=['Dianliang233'],
    desc='{wolframalpha.help.desc}',
    support_languages=['en_us'])


@w.handle('<query> {{wolframalpha.help}}')
async def _(msg: Bot.MessageSession):
    query = msg.parsed_msg['<query>']
    res = await asyncio.get_event_loop().run_in_executor(None, client.query, query)
    details = res.details
    answer = []
    images = []
    for title, detail in details.items():
        if title == 'Plot':
            continue
        answer.append(f'{title}: {detail}')
    # Parse out all images that don't have a plaintext counterpart
    for pod in res.pods:
        if pod.text is None and 'img' in pod.subpod:
            images.append(pod.subpod['img']['@src'])
    bot_images = [Image(image) for image in images]
    if await check_bool(' '.join(answer)):
        await msg.finish('https://wdf.ink/6OUp')
    else:
        await msg.finish(['\n'.join(answer), *bot_images])
