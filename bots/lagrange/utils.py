from bots.lagrange.client import bot
from aiocqhttp.exceptions import ActionFailed
from config import Config


def get_plain_msg(array_msg: list) -> str:
    text = []
    for msg in array_msg:
        if msg['type'] == 'text':
            text.append(msg['data']['text'])
    return '\n'.join(text)


async def get_group_list():
    return await bot.call_action('get_group_list')
