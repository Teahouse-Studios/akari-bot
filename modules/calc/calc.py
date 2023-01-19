import traceback

from constant import consts
from simpleeval import SimpleEval, DEFAULT_FUNCTIONS, DEFAULT_NAMES, DEFAULT_OPERATORS
import ast
import sys
import operator as op
import math
import statistics

funcs = {}


def add_func(module):
    for name in dir(math):
        item = getattr(math, name)
        if not name.startswith('_') and callable(item):
            funcs[name] = item


add_func(math)
add_func(statistics)

s_eval = SimpleEval(
    operators={
        **DEFAULT_OPERATORS,
        ast.BitOr: op.or_,
        ast.BitAnd: op.and_,
        ast.BitXor: op.xor,
        ast.Invert: op.invert,
    },
    functions={**funcs, **DEFAULT_FUNCTIONS},
    names={
        **DEFAULT_NAMES, **consts,
        'pi': math.pi,
        'e': math.e,
        'tau': math.tau,
        'inf': math.inf, 'nan': math.nan,
    }, )

try:  # rina's rina solution :rina:
    print('Result ' + str(s_eval.eval(' '.join(sys.argv[1:]))))
except Exception as e:
    print('Failed ' + str(e))
