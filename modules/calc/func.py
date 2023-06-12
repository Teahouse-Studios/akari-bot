import matplotlib.pyplot as plt
import numpy as np
import math
import sys

from core.utils.cache import random_cache_path
from simpleeval import simple_eval

def generate_function(expr, is_3d=False):
    x_range = (-10, 10)
    resolution = 100
    x = np.linspace(x_range[0], x_range[1], resolution)
    expression = expr.split()

    math_functions = {name: getattr(math, name) for name in dir(math) if not name.startswith('_')}

    if is_3d:
        y = np.linspace(x_range[0], x_range[1], resolution)
        X, Y = np.meshgrid(x, y)
        Z = np.zeros((resolution, resolution))

        for i in range(resolution):
            for j in range(resolution):
                Z[i, j] = simple_eval(expr, functions=math_functions, names={'x': X[i, j], 'y': Y[i, j]})

        fig = plt.figure()
        ax = fig.add_subplot(111, projection='3d')
        ax.plot_surface(X, Y, Z, cmap='viridis')

        ax.set_xlabel('X')
        ax.set_ylabel('Y')
        ax.set_zlabel('Z')
        ax.set_title('')
    else:
        for exp in expression:
            if exp.isnumeric():
                y = np.full_like(x, float(exp))
            else:
                try:
                    y = np.array([simple_eval(exp, functions=math_functions, names={'x': xi}) for xi in x])
                except Exception as e:
                    print(f"Error: {e}")
                    return
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

expr = sys.argv[1:]

try:
    if 'y' in expr:
        path = generate_function(expr, is_3d=True)
    else:
        path = generate_function(expr)

    sys.stdout.write('Result ' + str(path))
except Exception as e:
    sys.stdout.write(f'Failed {str(e)}')
sys.exit()