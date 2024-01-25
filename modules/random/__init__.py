import secrets
import string
import uuid

from core.builtins import Bot
from core.component import module

r = module('random', alias=['rand', 'rng'],
           developers=['Dianliang233'], desc='{random.help.desc}', )


@r.command('number <min> <max> {{random.help.number}}', )
async def _(msg: Bot.MessageSession, min: int, max: int):
    if min > max:
        random = secrets.randbelow(min - max + 1) + max
    else:
        random = secrets.randbelow(max - min + 1) + min

    await msg.finish('' + str(random))


@r.command('choice <choices> ... {{random.help.choice}}', )
async def _(msg: Bot.MessageSession):
    choices = [msg.parsed_msg.get('<choices>')] + msg.parsed_msg.get('...', [])
    await msg.finish(secrets.choice(choices))


@r.command('shuffle <cards> ... {{random.help.shuffle}}', )
async def _(msg: Bot.MessageSession):
    cards = [msg.parsed_msg.get('<cards>')] + msg.parsed_msg.get('...', [])
    x = cards.copy()
    for i in reversed(range(1, len(x))):
        # pick an element in x[:i+1] with which to exchange x[i]
        j = secrets.randbelow(i + 1)
        x[i], x[j] = x[j], x[i]
    await msg.finish(', '.join(x))


@r.command('uuid {{random.help.uuid}}', )
async def _(msg: Bot.MessageSession):
    await msg.finish(str(uuid.uuid4()))
