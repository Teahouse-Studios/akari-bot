import secrets
import uuid

from core.builtins import Bot
from core.component import module

r = module('random', alias={'rand': 'random', 'rng': 'random'},
           developers=['Dianliang233'], desc='{random.help.desc}', )


@r.handle('number <min> <max> {{random.help.number}}', )
async def _(msg: Bot.MessageSession):
    _min = msg.parsed_msg['<min>']
    _max = msg.parsed_msg['<max>']
    random = secrets.randbelow(int(_max) - int(_min) + 1) + int(_min)
    await msg.finish('' + str(random))


@r.handle('choice ... {{random.help.choice}}', )
async def _(msg: Bot.MessageSession):
    choices = msg.parsed_msg['...']
    await msg.finish(secrets.choice(choices))


@r.handle('uuid {{random.help.uuid}}', )
async def _(msg: Bot.MessageSession):
    await msg.finish(str(uuid.uuid4()))
