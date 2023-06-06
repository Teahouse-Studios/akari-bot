import random
import itertools

from core.builtins import Bot
from core.component import module
from simpleeval import seval

def calc(expression):
    try:
        return seval(expression)
    except:
        return None

def is_valid(expression):
    operators = ['+', '-', '*', '/']
    numbers = [str(i) for i in range(1, 10)]
    return all(char in numbers + operators + ['(', ')'] for char in expression)

def has_solution(numbers):
    permutations = list(itertools.permutations(numbers))
    operators = ['+', '-', '*', '/']
    expressions = list(itertools.product(operators, repeat=3))
    
    for perm in permutations:
        for expr in expressions:
            exp = '((( {} {} {} ) {} {} ) {} {} )'.format(perm[0], expr[0], perm[1], expr[1], perm[2], expr[2], perm[3])
            if calc(exp) == 24:
                return True
            exp = '(( {} {} {} ) {} ( {} {} {} ))'.format(perm[0], expr[0], perm[1], expr[1], perm[2], expr[2], perm[3])
            if calc(exp) == 24:
                return True
            exp = '( {} {} ( {} {} ( {} {} {} )))'.format(perm[0], expr[0], perm[1], expr[1], perm[2], expr[2], perm[3])
            if calc(exp) == 24:
                return True
    return False

tf = module('twenty_four', alias=['twentyfour', '24'],
               desc='{twenty_four.help.desc}', developers=['DoroWolf'])
play_state = {}


@tf.command('{{twenty_four.help}}')
async def _(msg: Bot.MessageSession):
    if msg.target.targetId in play_state and play_state[msg.target.targetId]['24']['active']: 
        await msg.finish(msg.locale.t('twenty_four.message.running'))
    play_state.update({msg.target.targetId: {'24': {'active': True}}})

    numbers = [random.randint(1, 13) for _ in range(4)]
    has_solution_flag = has_solution(numbers)

    answer = await msg.waitNextMessage(msg.locale.t('twenty_four.message', numbers=numbers))
    expression = answer.asDisplay(text_only=True)
    if play_state[msg.target.targetId]['24']['active']:
        if expression.lower() in ['无解', 'none']:
            if has_solution_flag:
                await answer.sendMessage(msg.locale.t('twenty_four.message.incorrect.have_solution'))
            else:
                await answer.sendMessage(msg.locale.t('twenty_four.message.correct'))
        elif is_valid(expression):
            result = calc(expression)
            if result == 24:
                await answer.sendMessage(msg.locale.t('twenty_four.message.correct'))
            else:
                await answer.sendMessage(msg.locale.t('twenty_four.message.incorrect'))
        else:
            await answer.sendMessage(msg.locale.t('twenty_four.message.incorrect.error'))
        play_state[msg.target.targetId]['24']['active'] = False



@tf.command('stop {{twenty_four.stop.help}}')
async def s(msg: Bot.MessageSession):
    state = play_state.get(msg.target.targetId, {}).get('24', False)
    if state:
        if state['active']:
            play_state[msg.target.targetId]['24']['active'] = False
            await msg.sendMessage(msg.locale.t('twenty_four.stop.message'))
        else:
            await msg.sendMessage(msg.locale.t('twenty_four.stop.message.other'))
    else:
        await msg.sendMessage(msg.locale.t('twenty_four.stop.message.none'))