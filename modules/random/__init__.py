import secrets
import uuid
import string

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
    length = int(msg.parsed_msg['<count>'])
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
        
    strings = ''.join(secrets.choice(characters) for _ in range(length))
    await msg.finish(strings)

    
@r.handle('uuid {{random.help.uuid}}', )
async def _(msg: Bot.MessageSession):
    await msg.finish(str(uuid.uuid4()))
