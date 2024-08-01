import ast
import cmath
import decimal
import fractions
import math
import operator as op
import statistics
import sys

from simpleeval import EvalWithCompoundTypes, DEFAULT_FUNCTIONS, DEFAULT_NAMES, DEFAULT_OPERATORS

from constant import consts
from utils import invoke

funcs = {}
named_funcs = {}

invoke()


def add_func(module):
    for name in dir(module):
        item = getattr(module, name)
        if not name.startswith('_') and callable(item):
            funcs[name] = item


def add_named_func(module):
    named_funcs[module.__name__] = {}
    for name in dir(module):
        item = getattr(module, name)
        if not name.startswith('_') and callable(item):
            named_funcs[module.__name__][name] = item


add_func(math)
add_func(statistics)
add_named_func(cmath)
add_named_func(decimal)
add_named_func(fractions)

s_eval = EvalWithCompoundTypes(
    operators={
        **DEFAULT_OPERATORS,
        ast.BitOr: op.or_,
        ast.BitAnd: op.and_,
        ast.BitXor: op.xor,
        ast.Invert: op.invert,
    },
    functions={**funcs, **DEFAULT_FUNCTIONS,
               'bin': bin,
               'bool': bool,
               'complex': complex,
               'divmod': divmod,
               'hex': hex,
               'len': len,
               'oct': oct,
               'round': round
               },
    names={
        **DEFAULT_NAMES, **consts, **named_funcs,
        'pi': math.pi,
        'e': math.e,
        'tau': math.tau,
        'inf': math.inf, 'nan': math.nan,
        'cmath': {
            'pi': cmath.pi,
            'e': cmath.e,
            'tau': cmath.tau,
            'inf': cmath.inf,
            'infj': cmath.infj,
            'nan': cmath.nan,
            'nanj': cmath.nanj,
            **named_funcs['cmath'],
        },
    }, )

try:  # rina's rina lazy solution :rina:
    res = s_eval.eval(' '.join(sys.argv[1:]))
    if abs(res) >= 10 ** 9 or abs(res) <= 10 ** -9:
        res = "{:.10e}".format(res)
    sys.stdout.write(f'Result {str(res)}')
except Exception as e:
    sys.stdout.write(f'Failed {str(e)}')
sys.exit()
