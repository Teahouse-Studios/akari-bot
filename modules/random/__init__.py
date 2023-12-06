import secrets
import string
import uuid

from core.builtins import Bot
from core.component import module

r = module('random', alias=['rand', 'rng'],
           developers=['Dianliang233', 'DoroWolf'], desc='{random.help.desc}', )


@r.command('number <min> <max> {{random.help.number}}', )
async def _(msg: Bot.MessageSession, min: int, max: int):
    if min > max:
        random = secrets.randbelow(min - max + 1) + max
    else:
        random = secrets.randbelow(max - min + 1) + min

    await msg.finish('' + str(random))


@r.command('choice ... {{random.help.choice}}', )
async def _(msg: Bot.MessageSession):
    choices = msg.parsed_msg['...']
    await msg.finish(secrets.choice(choices))


@r.command('shuffle ... {{random.help.shuffle}}', )
async def _(msg: Bot.MessageSession):
    cards: list = msg.parsed_msg['...']
    x = cards.copy()
    for i in reversed(range(1, len(x))):
        # pick an element in x[:i+1] with which to exchange x[i]
        j = secrets.randbelow(i + 1)
        x[i], x[j] = x[j], x[i]
    await msg.finish(', '.join(x))


@r.command('password <length> [-u] [-l] [-n] [-s] {{random.help.password}}',
          options_desc={'-u': '{random.help.option.password.u}',
                        '-l': '{random.help.option.password.l}',
                        '-n': '{random.help.option.password.n}',
                        '-s': '{random.help.option.password.s}'})
async def _(msg: Bot.MessageSession, length: int):
    if length < 1 or length > 100:
        return await msg.finish(msg.locale.t('random.message.password.error.invalid'))
    characters = ""
    if msg.parsed_msg.get('-u', False):
        characters += string.ascii_uppercase
    if msg.parsed_msg.get('-l', False):
        characters += string.ascii_lowercase
    if msg.parsed_msg.get('-n', False):
        characters += string.digits
    if msg.parsed_msg.get('-s', False):
        characters += "!@#$%^&*-_+=?"

    if not characters:
        characters = string.ascii_letters + string.digits

    random = ''.join(secrets.choice(characters) for _ in range(length))
    await msg.finish(random)


@r.command('uuid {{random.help.uuid}}', )
async def _(msg: Bot.MessageSession):
    await msg.finish(str(uuid.uuid4()))
