import re

from mpl_toolkits.mplot3d import Axes3D
import numpy as np
from matplotlib import pyplot as plt

plt.rcParams['font.family'] = ['NotoSansXJB']
plt.rcParams['axes.unicode_minus'] = False


async def function_rend(type, data: dict):
    if type == '11f':
        x = f"np.arange({data['x']})"
        pattern = re.compile(r'[\[\]]')
        x = eval(pattern.sub(repl='', string=x))
        y = 2 * x
        plt.xlabel('x')
        plt.ylabel('y')
        plt.title("一元一次函数")
        plt.plot(x, y)
    elif type == '12f':
        x = f"np.arange({data['x']})"
        pattern = re.compile(r'[\[\]]')
        x = eval(pattern.sub(repl='', string=x))
        y = x * x
        plt.xlabel('x')
        plt.ylabel('y')
        plt.title("一元二次函数")
        plt.plot(x, y)
    elif type == 'ef':
        x = f"np.arange({data['x']})"
        pattern = re.compile(r'[\[\]]')
        x = eval(pattern.sub(repl='', string=x))
        y = np.power(2, x)
        plt.xlabel('x')
        plt.ylabel('y')
        plt.title("指数函数")
        plt.plot(x, y)
    elif type == 'sf':
        data_ = data['x']
        data_[1] = data_[1] * np.pi
        data_[2] = data_[2] * np.pi
        x = f"np.arange({data_})"
        pattern = re.compile(r'[\[\]]')
        x = eval(pattern.sub(repl='', string=x))
        y = np.sin(x)
        plt.xlabel('x')
        plt.ylabel('y')
        plt.title("正弦函数")
        plt.plot(x, y)
    elif type == 'cf':
        data_ = data['x']
        data_[1] = data_[1] * np.pi
        data_[2] = data_[2] * np.pi
        x = f"np.arange({data_})"
        pattern = re.compile(r'[\[\]]')
        x = eval(pattern.sub(repl='', string=x))
        y = np.cos(x)
        plt.xlabel('x')
        plt.ylabel('y')
        plt.title("正弦函数")
        plt.plot(x, y)
    elif type == '21f':
        fig = plt.figure()
        ax = Axes3D(fig)
        x = f"np.arange({data['x']})"
        pattern = re.compile(r'[\[\]]')
        x = eval(pattern.sub(repl='', string=x))
        y = f"np.arange({data['y']})"
        pattern = re.compile(r'[\[\]]')
        y = eval(pattern.sub(repl='', string=y))
        X, Y = np.meshgrid(x, y)
        Z = X + Y
        plt.xlabel('x')
        plt.ylabel('y')
        ax.plot_surface(X, Y, Z, rstride=1, cstride=1, cmap='rainbow')
    elif type == '22f':
        fig = plt.figure()
        ax = Axes3D(fig)
        x = f"np.arange({data['x']})"
        pattern = re.compile(r'[\[\]]')
        x = eval(pattern.sub(repl='', string=x))
        y = f"np.arange({data['y']})"
        pattern = re.compile(r'[\[\]]')
        y = eval(pattern.sub(repl='', string=y))
        X, Y = np.meshgrid(x, y)
        Z = X * X + Y * Y
        plt.xlabel('x')
        plt.ylabel('y')
        ax.plot_surface(X, Y, Z, rstride=1, cstride=1, cmap='rainbow')

    return plt.
