import secrets

from core.builtins.message import MessageSession
from core.component import on_command

r = on_command('random', alias={'rand': 'random', 'rng': 'random', 'dice': 'random number 1 6',
                                'random dice': 'random number 1 6', 'coin': 'random choice 正面 反面',
                                'random coin': 'random choice 正面 反面'}, developers=[
    'Dianliang233'], desc='随机数生成器（密码学安全）', )


@r.handle('number <min> <max> {生成区间内的随机整数}', )
async def _(msg: MessageSession):
    _min = msg.parsed_msg['<min>']
    _max = msg.parsed_msg['<max>']
    random = secrets.randbelow(int(_max) - int(_min) + 1) + int(_min)
    await msg.finish('' + str(random))


@r.handle('choice ... {从集合中选择元素}', )
async def _(msg: MessageSession):
    choices = msg.parsed_msg['...']
    await msg.finish(secrets.choice(choices))
