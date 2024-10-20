import uuid

from core.builtins import Bot
from core.component import module
from core.utils.random import Random

r = module('random', alias=['rand', 'rng'],
           developers=['Dianliang233'], desc='{random.help.desc}', doc=True)


@r.command('number <min> <max> {{random.help.number}}')
async def _(msg: Bot.MessageSession, min: int, max: int):
    if min > max:
        random = Random.randint(max, min)
    else:
        random = Random.randint(min, max)

    await msg.finish('' + str(random))


@r.command('choice <choices> ... {{random.help.choice}}')
async def _(msg: Bot.MessageSession):
    choices = [msg.parsed_msg.get('<choices>')] + msg.parsed_msg.get('...', [])
    await msg.finish(Random.choice(choices))


@r.command('shuffle <cards> ... {{random.help.shuffle}}')
async def _(msg: Bot.MessageSession):
    cards = [msg.parsed_msg.get('<cards>')] + msg.parsed_msg.get('...', [])
    x = Random.shuffle(cards)
    await msg.finish(', '.join(x))


@r.command('uuid {{random.help.uuid}}')
async def _(msg: Bot.MessageSession):
    await msg.finish(str(uuid.uuid4()))
