import secrets
import uuid
import string

from core.builtins import Bot
from core.component import module

r = module('random', alias={'rand': 'random', 'rng': 'random'},
           developers=['Dianliang233', 'DoroWolf'], desc='{random.help.desc}', )


@r.handle('number <min> <max> {{random.help.number}}', )
async def _(msg: Bot.MessageSession):
    try:
        _min = int(msg.parsed_msg['<min>'])
        _max = int(msg.parsed_msg['<max>'])
    if _min > _max:
        return await msg.finish(msg.locale.t('random.message.number.error.out_of_range'))
    except ValueError:
        return await msg.finish(msg.locale.t('random.message.number.error.invalid'))
    random = secrets.randbelow(_max - _min + 1) + _min
    await msg.finish('' + str(random))


@r.handle('choice ... {{random.help.choice}}', )
async def _(msg: Bot.MessageSession):
    choices = msg.parsed_msg['...']
    await msg.finish(secrets.choice(choices))


@r.handle('shuffle ... {{random.help.shuffle}}', )
async def _(msg: Bot.MessageSession):
    cards: list = msg.parsed_msg['...']
    x = cards.copy()
    for i in reversed(range(1, len(x))):
        # pick an element in x[:i+1] with which to exchange x[i]
        j = secrets.randbelow(i + 1)
        x[i], x[j] = x[j], x[i]
    await msg.finish(', '.join(x))

@r.handle('string <count> [-u] [-l] [-n] [-s] {{random.help.string}}', 
         options_desc={'-u': '{random.help.string.u}', 
                      '-l': '{random.help.string.l}', 
                      '-n': '{random.help.string.n}', 
                      '-s': '{random.help.string.s}'})
async def _(msg: Bot.MessageSession):

    try:
        length = int(msg.parsed_msg['<count>'])
        if length < 1 or length > 100:
            raise ValueError
    except ValueError:
        return await msg.finish(msg.locale.t('random.message.string.error.invalid'))
    characters = ""
    if msg.parsed_msg.get('-u', False):
            characters += string.ascii_uppercase
    if msg.parsed_msg.get('-l', False):
            characters += string.ascii_lowercase
    if msg.parsed_msg.get('-n', False):
            characters += string.digits
    if msg.parsed_msg.get('-s', False):
            characters += string.punctuation

    if not characters:
        characters = string.ascii_letters + string.digits
        
    random = ''.join(secrets.choice(characters) for _ in range(length))
    await msg.finish(random)

    
@r.handle('uuid {{random.help.uuid}}', )
async def _(msg: Bot.MessageSession):
    await msg.finish(str(uuid.uuid4()))
