import matplotlib.pyplot as plt
import numpy as np
import math
import sys

from core.utils.cache import random_cache_path
from utils import do_something
from simpleeval import simple_eval

do_something()

def generate_function(expr):
    x_range = (-10, 10)
    resolution = 100
    x = np.linspace(x_range[0], x_range[1], resolution)
    expression = expr.split()

    math_functions = {name: getattr(math, name) for name in dir(math) if not name.startswith('_')}

    for exp in expression:
        if exp.isnumeric():
            y = np.full_like(x, float(exp))
        else:
            y = np.array([simple_eval(exp, functions=math_functions, names={'x': xi}) for xi in x])
        label = f'f(x)={exp}'

        plt.plot(x, y, label=label)

    plt.xlabel('x')
    plt.ylabel('y')
    plt.title('')
    plt.grid(True)
    plt.legend()

    path = random_cache_path() + '.png'
    plt.savefig(path)
    plt.close()

    return path

expr = ''.join(sys.argv[1:])

try:
    path = generate_function(expr)

    sys.stdout.write('Result ' + str(path))
except Exception as e:
    sys.stdout.write(f'Failed {str(e)}')
sys.exit()