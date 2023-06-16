import asyncio
import os
import subprocess
import sys
import re
import traceback

from core.builtins import Bot, Image
from core.component import on_command
from core.exceptions import NoReportException
from core.logger import Logger
from numpy import median, var, average
from scipy import stats
from ast import literal_eval
from .function import *

c = on_command('calc', developers=[
    'Dianliang233', 'haoye_qwq'], alias={'calc chemical_equation': 'calc ce'}, desc='计算器')


@c.handle('<math_expression> {安全地计算Python ast表达式}', options_desc={'+': '和/正数：1 + 2 -> 3',
                                                                          '-': '差/负数：3 - 1 -> 2',
                                                                          '/': '商：6 / 3 -> 2',
                                                                          '*': '积：2 * 3 -> 6',
                                                                          '**': 'x 的 y 次幂（由于性能问题，指数不得超过 4e+6）：2 ** 3 '
                                                                                '-> 8',
                                                                          '%': '取模：5 % 2 -> 1',
                                                                          '==': '等于：1 == 1 -> True',
                                                                          '<=': '小于等于：1 <= 2 -> True',
                                                                          '>=': '大于等于：1 >= 2 -> False',
                                                                          '>>': 'x 右移 y 位（相当于 x / (2 ** y)，y < '
                                                                                '10000）：32 >> 5 -> 1',
                                                                          '<<': 'x 左移 y 位（相当于 x * (2 ** y)，y < '
                                                                                '10000）：1 << 5 -> 32',
                                                                          '^': '按位异或：1 ^ 1 -> 0',
                                                                          'not': '非：not True -> False',
                                                                          'is': 'x 与 y 是同一个对象：1 is 1 -> True',
                                                                          'randint(x)': '小于 x 的随机整数：randint(6) -> 5',
                                                                          'rand()': '0 与 1 之间的随机浮点数：rand() -> '
                                                                                    '0.5789015836448923',
                                                                          'int()': '转换为整数：int(1.5) -> 1',
                                                                          'float()': '转换为浮点数：float(1) -> 1.0',
                                                                          'str()': '转换为字符串：str(1) -> "1"',
                                                                          'complex()': '转换为复数：complex(1) -> (1 + 0j)',
                                                                          'bool()': '转换为布尔值：bool(1) -> True',
                                                                          'bin()': '转换为二进制：bin(268) -> 0b100001100',
                                                                          'oct()': '转换为八进制：oct(268) ->  0o414',
                                                                          'hex()': '转换为十六进制：hex(268) -> 0x10c',
                                                                          '更多可用运算符和函数': 'https://bot.teahouse.team'
                                                                                                  '/-/340', })
async def _(msg: Bot.MessageSession):
    expr = msg.asDisplay().split(' ', 1)[1]
    if sys.platform == 'win32' and sys.version_info.minor < 10:
        try:
            res = subprocess.check_output(
                ['python', os.path.abspath("./modules/calc/calc.py"), expr], timeout=10, shell=False).decode('utf-8')
            if res[0:6] == 'Result':
                await msg.finish(f'{expr} = {res[7:]}')
            else:
                await msg.finish(f'表达式无效：{res[7:]}')
        except subprocess.TimeoutExpired:
            raise NoReportException('计算超时。')
    else:
        try:
            p = await asyncio.create_subprocess_exec('python', os.path.abspath("./modules/calc/calc.py"), expr,
                                                     stdout=asyncio.subprocess.PIPE,
                                                     stderr=asyncio.subprocess.PIPE
                                                     )
            try:
                await asyncio.wait_for(p.wait(), timeout=10)
            except asyncio.TimeoutError:
                p.kill()
                raise NoReportException('计算超时。')
            stdout_data, stderr_data = await p.communicate()
            if p.returncode == 0:
                res = stdout_data.decode('utf-8')

                if res[0:6] == 'Result':
                    await msg.finish(f'{expr} = {res[7:]}')
                else:
                    await msg.finish(f'表达式无效：{res[7:]}')
            else:
                Logger.error(f'calc.py exited with code {p.returncode}')
                try:
                    Logger.error(
                        f'calc.py stderr: {stderr_data.decode("utf-8")}')
                except UnicodeDecodeError:
                    Logger.error(
                        f'calc.py stderr: {stderr_data.decode("gbk")}')
        except Exception as e:
            raise NoReportException(e)


@c.handle('function <function> {绘制函数图像}')
async def func(msg: Bot.MessageSession):
    img = await func_img(str(msg.parsed_msg['<function>']))
    await msg.sendMessage(Image(img))
    await msg.sleep(10)
    os.remove(img)


@c.handle('count <text> {统计文字字数}')
async def count(msg: Bot.MessageSession):
    text = msg.parsed_msg['<text>'].replace(' ', '').chomp
    symbol = re.findall(
        r'[`~!@#$%^&*()_\\\-+=<>?:\"{}|,./;\'\[\]·！￥…（）—\-+《》？：“”【】、；‘，。]',
        msg.parsed_msg['<text>'].replace(' ', ''))
    for i in symbol:
        text = text.replace(i, '')
    if text is None:
        count_text = 0
    else:
        count_text = len(text)
    if symbol is None:
        count_symbol = 0
    else:
        count_symbol = len(symbol)
    await msg.sendMessage(
        f"字符数: {len(msg.parsed_msg['<text>'].replace(' ', '').chomp)}\n字数: {count_text}\n符号数: {count_symbol}"
    )


@c.handle('mode <num-list> {众数}')
async def mode(msg: Bot.MessageSession):
    try:
        num_l = msg.parsed_msg['<num-list>'].replace('【', '[').replace('】', ']').replace('，', ',')
        await msg.sendMessage(f"数组 {num_l} 的众数是 {stats(literal_eval(num_l))}")
    except Exception:
        await msg.sendMessage('出错了，请检查数据类型')
        traceback.print_exc()


@c.handle('median <num-list> {中位数}')
async def median(msg: Bot.MessageSession):
    try:
        num_l = msg.parsed_msg['<num-list>'].replace('【', '[').replace('】', ']').replace('，', ',')
        await msg.sendMessage(f"数组 {num_l} 的中位数是 {median(literal_eval(num_l))}")
    except Exception:
        await msg.sendMessage('出错了，请检查数据类型')
        traceback.print_exc()


@c.handle('var <num-list> {方差}')
async def var(msg: Bot.MessageSession):
    try:
        num_l = msg.parsed_msg['<num-list>'].replace('【', '[').replace('】', ']').replace('，', ',')
        await msg.sendMessage(f"数组 {num_l} 的方差是 {var(literal_eval(num_l))}")
    except Exception:
        await msg.sendMessage('出错了，请检查数据类型')
        traceback.print_exc()


@c.handle('mean <num-list> <weights> {加权平均数}')
async def mean(msg: Bot.MessageSession):
    try:
        num_l = msg.parsed_msg['<num-list>'].replace('【', '[').replace('】', ']').replace('，', ',')
        weights = msg.parsed_msg['<weights>'].replace('【', '[').replace('】', ']').replace('，', ',')
        if len(literal_eval(num_l)) == len(literal_eval(weights)):
            await msg.sendMessage(
                f"数组 {num_l} 权 {weights} 的加权平均数为 {average(literal_eval(num_l), weights=literal_eval(weights))}")
        else:
            await msg.sendMessage('数组与权未一一对应')
    except Exception:
        await msg.sendMessage('出错了，请检查数据类型')
        traceback.print_exc()
