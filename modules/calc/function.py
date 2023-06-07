import random
import numpy as np
from scipy.interpolate import interp1d
from matplotlib import pyplot as plt


async def func_img(function: str):
    if 'x' and 'y=' in function.replace(' ', ''):
        function = function.replace('^', '**').replace('÷', '/').replace('×', '*')\
            .replace('（', '(').replace('）', ')').replace('。', '.').replace('y=', '').replace(' ', '')
        xa = np.array([1, 2, 3, 4, 5, 6, 7])
        ya = []
        for i in [1, 2, 3, 4, 5, 6, 7]:
            ya.append(eval(str(function.replace('x', str(i))), {"__builtins__": None}))
        cubic_interploation_model = interp1d(xa, np.array(ya), kind="cubic")
        xs = np.linspace(1, 7, 500)
        ys = cubic_interploation_model(xs)
        plt.gca().set_aspect(1)
        plt.plot(xs, ys)
        plt.title('y='+function)
        plt.xlabel('x-axis')
        plt.ylabel('y-axis')
        name = './cache/'+str(random.randint(100000000, 20000000000000000))+'.png'
        plt.savefig(name, dpi=200)
        plt.close()
        return name
    else:
        return '表达式应是y=(关于x的式子)函数解析式的形式'
