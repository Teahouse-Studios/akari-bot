import asyncio
import os
import subprocess
import sys
import time

from core.builtins import Bot, Plain, Image
from core.component import module
from core.exceptions import NoReportException
from core.logger import Logger

calc_dir = os.path.dirname(os.path.abspath(__file__))

c = module('calc', developers=[
    'Dianliang233'], desc='{calc.help.calc.desc}')


@c.command('<math_expression>', options_desc={'+': '{calc.help.calc.option.plus}',
                                              '-': '{calc.help.calc.option.minus}',
                                              '/': '{calc.help.calc.option.multiply}',
                                              '*': '{calc.help.calc.option.divide}',
                                              '**': '{calc.help.calc.option.power}',
                                              '%': '{calc.help.calc.option.modulo}',
                                              '==': '{calc.help.calc.option.equal}',
                                              '<=': '{calc.help.calc.option.less_equal}',
                                              '>=': '{calc.help.calc.option.greater_equal}',
                                              '>>': '{calc.help.calc.option.move_right}',
                                              '<<': '{calc.help.calc.option.move_left}',
                                              '^': '{calc.help.calc.option.xor}',
                                              'not': '{calc.help.calc.option.not}',
                                              'is': '{calc.help.calc.option.is}',
                                              'randint(x)': '{calc.help.calc.option.randint}',
                                              'rand()': '{calc.help.calc.option.rand}',
                                              'int()': '{calc.help.calc.option.int}',
                                              'float()': '{calc.help.calc.option.float}',
                                              'str()': '{calc.help.calc.option.str}',
                                              'complex()': '{calc.help.calc.option.complex}',
                                              'bool()': '{calc.help.calc.option.bool}',
                                              'bin()': '{calc.help.calc.option.bin}',
                                              'oct()': '{calc.help.calc.option.oct}',
                                              'hex()': '{calc.help.calc.option.hex}',
                                              '{calc.help.calc.option.more}': 'https://bot.teahouse.team/-/340',
                                              })
async def _(msg: Bot.MessageSession):
    expr = msg.asDisplay().split(' ', 1)[1]
    start = time.perf_counter_ns()
    res = await spawn_subprocess('/calc.py', expr, msg)
    stop = time.perf_counter_ns()
    delta = (stop - start) / 1000000
    if res[:6] == 'Result':
        if msg.target.senderFrom == "Discord|Client":
            m = f'`{(expr)}` = {res[7:]}'
        else:
            m = f'{(expr)} = {res[7:]}'
        if msg.checkSuperUser():
            m += '\n' + msg.locale.t("calc.message.running_time", time=delta)
        await msg.finish(m)
    else:
        await msg.finish(msg.locale.t("calc.message.calc.invalid", expr={res[7:]}))


func = module('func',
              developers=['DoroWolf'],
              recommend_modules=['calc'], required_superuser=True)


@func.handle('<math_expression> {{calc.help.func}}')
async def _(msg: Bot.MessageSession):
    expr = msg.asDisplay().split(' ', 1)[1]
    start = time.perf_counter_ns()
    res = await spawn_subprocess('/func.py', expr, msg)
    stop = time.perf_counter_ns()
    delta = (stop - start) / 1000000
    if res[:6] == 'Result':
        img = Image(res[7:])
        if msg.checkSuperUser():
            txt = Plain(msg.locale.t("calc.message.running_time", time=delta))
            m = [img, txt]
        else:
            m = img
        await msg.finish(m)
    else:
        await msg.finish(msg.locale.t("calc.message.calc.invalid", expr={res[7:]}))


async def spawn_subprocess(file: str, arg: str, msg: Bot.MessageSession) -> str:
    envs = os.environ.copy()
    if sys.platform == 'win32' and sys.version_info.minor < 10:
        try:
            return subprocess.check_output(
                [sys.executable, calc_dir + file, arg], timeout=10, shell=False,
                cwd=os.path.abspath('.'), env=envs) \
                .decode('utf-8')
        except subprocess.TimeoutExpired as e:
            raise NoReportException(msg.locale.t("calc.message.time_out")) from e
    else:
        try:
            p = await asyncio.create_subprocess_exec(sys.executable, calc_dir + file,
                                                     arg,
                                                     stdout=asyncio.subprocess.PIPE,
                                                     stderr=asyncio.subprocess.PIPE,
                                                     cwd=os.path.abspath('.'), env=envs
                                                     )
            try:
                await asyncio.wait_for(p.wait(), timeout=10)
            except asyncio.TimeoutError as e:
                p.kill()
                raise NoReportException(msg.locale.t("calc.message.time_out")) from e
            stdout_data, stderr_data = await p.communicate()
            if p.returncode != 0:
                Logger.error(f'{file} exited with code {p.returncode}')
                try:
                    Logger.error(
                        f'{file} stderr: {stderr_data.decode("utf-8")}')
                except UnicodeDecodeError:
                    Logger.error(
                        f'{file} stderr: {stderr_data.decode("gbk")}')
            return stdout_data.decode('utf-8')
        except Exception as e:
            raise NoReportException(e) from e
