import asyncio
import os
import subprocess
import sys
import time

import ujson as json

from core.builtins import Bot
from core.component import module
from core.exceptions import NoReportException
from core.logger import Logger

calc_dir = os.path.dirname(os.path.abspath(__file__))

c = module('calc', developers=[
    'Dianliang233'], desc='{calc.help.calc.desc}')


@c.command('<math_expression>', options_desc={'+': '{calc.help.calc.plus}',
                                              '-': '{calc.help.calc.minus}',
                                              '/': '{calc.help.calc.multiply}',
                                              '*': '{calc.help.calc.divide}',
                                              '**': '{calc.help.calc.power}',
                                              '%': '{calc.help.calc.modulo}',
                                              '==': '{calc.help.calc.equal}',
                                              '<=': '{calc.help.calc.less_equal}',
                                              '>=': '{calc.help.calc.greater_equal}',
                                              '>>': '{calc.help.calc.move_right}',
                                              '<<': '{calc.help.calc.move_left}',
                                              '^': '{calc.help.calc.xor}',
                                              'not': '{calc.help.calc.not}',
                                              'is': '{calc.help.calc.is}',
                                              'randint(x)': '{calc.help.calc.randint}',
                                              'rand()': '{calc.help.calc.rand}',
                                              'int()': '{calc.help.calc.int}',
                                              'float()': '{calc.help.calc.float}',
                                              'str()': '{calc.help.calc.str}',
                                              'complex()': '{calc.help.calc.complex}',
                                              'bool()': '{calc.help.calc.bool}',
                                              'bin()': '{calc.help.calc.bin}',
                                              'oct()': '{calc.help.calc.oct}',
                                              'hex()': '{calc.help.calc.hex}',
                                              '{calc.help.calc.more}': 'https://bot.teahouse.team/-/340',
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


factor = module('factor', 
        developers=['DoroWolf', 'Light-Beacon', 'Dianliang233'], 
        recommend_modules=['calc'])


@factor.handle('prime <number> {{calc.help.factor.prime}}')
async def prime(msg: Bot.MessageSession):
    try:
        num = int(msg.parsed_msg.get('<number>'))
        if num <= 1:
            raise ValueError
    except ValueError:
        return await msg.finish(msg.locale.t('calc.message.factor.prime.error'))
    start = time.perf_counter_ns()
    res = await spawn_subprocess('/factor.py', str(num), msg)
    stop = time.perf_counter_ns()
    delta = (stop - start) / 1000000
    if res[:6] != 'Result':
        raise ValueError(res)
    primes = json.loads(res[7:])
    prime = "*".join(primes)
    if len(primes) == 1:
        m = msg.locale.t("calc.message.factor.prime.is_prime", num=num)
    else:
        m = (
            f'{num} = `{prime}`'
            if msg.target.senderFrom == "Discord|Client"
            else f'{num} = {prime}'
        )
    if msg.checkSuperUser():
        m += '\n' + msg.locale.t("calc.message.running_time", time=delta)
    await msg.finish(m)


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
