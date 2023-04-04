import asyncio
import os
import subprocess
import sys

from core.builtins import Bot, Image
from core.component import on_command
from core.exceptions import NoReportException
from core.logger import Logger
from .function import *
from .ChemicalEquation import *

c = on_command('calc', developers=[
    'Dianliang233', 'haoye_qwq'], alias={'calc chemical_equation': 'calc ce'}, desc='安全地计算 Python ast 表达式。')


@c.handle('<math_expression>', options_desc={'+': '和/正数：1 + 2 -> 3',
                                             '-': '差/负数：3 - 1 -> 2',
                                             '/': '商：6 / 3 -> 2',
                                             '*': '积：2 * 3 -> 6',
                                             '**': 'x 的 y 次幂（由于性能问题，指数不得超过 4e+6）：2 ** 3 -> 8',
                                             '%': '取模：5 % 2 -> 1',
                                             '==': '等于：1 == 1 -> True',
                                             '<=': '小于等于：1 <= 2 -> True',
                                             '>=': '大于等于：1 >= 2 -> False',
                                             '>>': 'x 右移 y 位（相当于 x / (2 ** y)，y < 10000）：32 >> 5 -> 1',
                                             '<<': 'x 左移 y 位（相当于 x * (2 ** y)，y < 10000）：1 << 5 -> 32',
                                             '^': '按位异或：1 ^ 1 -> 0',
                                             'not': '非：not True -> False',
                                             'is': 'x 与 y 是同一个对象：1 is 1 -> True',
                                             'randint(x)': '小于 x 的随机整数：randint(6) -> 5',
                                             'rand()': '0 与 1 之间的随机浮点数：rand() -> 0.5789015836448923',
                                             'int()': '转换为整数：int(1.5) -> 1',
                                             'float()': '转换为浮点数：float(1) -> 1.0',
                                             'str()': '转换为字符串：str(1) -> "1"',
                                             'complex()': '转换为复数：complex(1) -> (1 + 0j)',
                                             'bool()': '转换为布尔值：bool(1) -> True',
                                             'bin()': '转换为二进制：bin(268) -> 0b100001100',
                                             'oct()': '转换为八进制：oct(268) ->  0o414',
                                             'hex()': '转换为十六进制：hex(268) -> 0x10c',
                                             '更多可用运算符和函数': 'https://bot.teahouse.team/-/340',
                                             })
async def _(msg: Bot.MessageSession):
    expr = msg.asDisplay().split(' ', 1)[1]
    if sys.platform == 'win32' and sys.version_info.minor < 10:
        try:
            res = subprocess.check_output(
                ['python', os.path.abspath("./modules/calc/calc.py"), expr], timeout=10, shell=False).decode('utf-8')
            if res[0:6] == 'Result':
                await msg.finish(f'{(expr)} = {res[7:]}')
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
                    await msg.finish(f'{(expr)} = {res[7:]}')
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


# @c.handle('function <type> <x> {函数计算}',
#           options_desc={'type': ['11f:一元一次函数', '12f:一元二次函数', 'ef:指数函数', 'sf:正弦函数', 'cf:余弦函数']})
# async def _(send: Bot.MessageSession):
#     type = send.parsed_msg['<type>']
#     data = {'x': f"{send.parsed_msg['<x>']}", 'y': None}
#     await send.sendMessage(Image(function_rend(str(type), data)))
# 没写好.jpg

@c.handle('chemical_equation <chemical_equation> {化学方程式配平}')
async def ce(send: Bot.MessageSession):
    ce_ = send.parsed_msg['<chemical_equation>']
    await send.sendMessage(Str2Equ(ce_))
