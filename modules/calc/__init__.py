import asyncio
import os
import subprocess
import sys
import time

from core.builtins import Bot
from core.component import module
from core.exceptions import NoReportException
from core.logger import Logger

calc_dir = os.path.dirname(os.path.abspath(__file__))

c = module('calc', developers=[
    'Dianliang233'], desc='{calc.help.desc}')


@c.command('<math_expression>', options_desc={'+': '{calc.help.option.plus}',
                                              '-': '{calc.help.option.minus}',
                                              '/': '{calc.help.option.multiply}',
                                              '*': '{calc.help.option.divide}',
                                              '**': '{calc.help.option.power}',
                                              '%': '{calc.help.option.modulo}',
                                              '==': '{calc.help.option.equal}',
                                              '<=': '{calc.help.option.less_equal}',
                                              '>=': '{calc.help.option.greater_equal}',
                                              '>>': '{calc.help.option.move_right}',
                                              '<<': '{calc.help.option.move_left}',
                                              '^': '{calc.help.option.xor}',
                                              'not': '{calc.help.option.not}',
                                              'is': '{calc.help.option.is}',
                                              'randint(x)': '{calc.help.option.randint}',
                                              'rand()': '{calc.help.option.rand}',
                                              'int()': '{calc.help.option.int}',
                                              'float()': '{calc.help.option.float}',
                                              'str()': '{calc.help.option.str}',
                                              'complex()': '{calc.help.option.complex}',
                                              'bool()': '{calc.help.option.bool}',
                                              'bin()': '{calc.help.option.bin}',
                                              'oct()': '{calc.help.option.oct}',
                                              'hex()': '{calc.help.option.hex}',
                                              '{calc.help.option.more}': 'https://bot.teahouse.team/-/340',
                                              })
async def _(msg: Bot.MessageSession):
    expr = msg.as_display().split(' ', 1)[1]
    start = time.perf_counter_ns()
    res = await spawn_subprocess('/calc.py', expr, msg)
    stop = time.perf_counter_ns()
    delta = (stop - start) / 1000000
    if res[:6] == 'Result':
        if msg.target.sender_from == "Discord|Client":
            m = f'`{(expr)}` = {res[7:]}'
        else:
            m = f'{(expr)} = {res[7:]}'
        if msg.check_super_user():
            m += '\n' + msg.locale.t("calc.message.running_time", time=delta)
        await msg.finish(m)
    else:
        await msg.finish(msg.locale.t("calc.message.invalid", expr={res[7:]}))


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
