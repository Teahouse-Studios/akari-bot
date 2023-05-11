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
    'Dianliang233'], desc='{calc.calc.help.desc}')


@c.command('<math_expression>', options_desc={'+': '{calc.calc.help.plus}',
                                              '-': '{calc.calc.help.minus}',
                                              '/': '{calc.calc.help.multiply}',
                                              '*': '{calc.calc.help.divide}',
                                              '**': '{calc.calc.help.power}',
                                              '%': '{calc.calc.help.modulo}',
                                              '==': '{calc.calc.help.equal}',
                                              '<=': '{calc.calc.help.less_equal}',
                                              '>=': '{calc.calc.help.greater_equal}',
                                              '>>': '{calc.calc.help.move_right}',
                                              '<<': '{calc.calc.help.move_left}',
                                              '^': '{calc.calc.help.xor}',
                                              'not': '{calc.calc.help.not}',
                                              'is': '{calc.calc.help.is}',
                                              'randint(x)': '{calc.calc.help.randint}',
                                              'rand()': '{calc.calc.help.rand}',
                                              'int()': '{calc.calc.help.int}',
                                              'float()': '{calc.calc.help.float}',
                                              'str()': '{calc.calc.help.str}',
                                              'complex()': '{calc.calc.help.complex}',
                                              'bool()': '{calc.calc.help.bool}',
                                              'bin()': '{calc.calc.help.bin}',
                                              'oct()': '{calc.calc.help.oct}',
                                              'hex()': '{calc.calc.help.hex}',
                                              '{calc.calc.help.more}': 'https://bot.teahouse.team/-/340',
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
        await msg.finish(msg.locale.t("calc.calc.message.invalid", expr={res[7:]}))


factor = module('factor', developers=['DoroWolf, Light-Beacon', 'Dianliang233'])


@factor.handle('prime <number> {{calc.factor.prime.help}}')
async def prime(msg: Bot.MessageSession):
    try:
        num_str = msg.parsed_msg.get('<number>')
        if num_str is None:
            raise ValueError
        num = int(num_str)
        if num <= 1:
            return await msg.finish(msg.locale.t('calc.factor.prime.message.error'))
    except ValueError:
        return await msg.finish(msg.locale.t('calc.factor.prime.message.error'))
    start = time.perf_counter_ns()
    res = await spawn_subprocess('/factor.py', str(num), msg)
    stop = time.perf_counter_ns()
    delta = (stop - start) / 1000000
    if res[:6] != 'Result':
        raise ValueError(res)
    primes = json.loads(res[7:])
    prime = "*".join(primes)
    if len(primes) == 1:
        m = msg.locale.t("calc.factor.prime.message.is_prime", num=num)
    m = (
        f'`{num}` = {prime}'
        if msg.target.senderFrom == "Discord|Client"
        else f'{num} = {prime}'
    )
    if msg.checkSuperUser():
        m += '\n' + msg.locale.t("calc.message.running_time", time=delta)
    await msg.finish(m)


async def spawn_subprocess(file: str, input: str, msg: Bot.MessageSession) -> str:
    envs = os.environ.copy()
    if sys.platform == 'win32' and sys.version_info.minor < 10:
        try:
            return subprocess.check_output(
                [sys.executable, calc_dir + file, input], timeout=10, shell=False,
                cwd=os.path.abspath('.'), env=envs) \
                .decode('utf-8')
        except subprocess.TimeoutExpired as e:
            raise NoReportException(msg.locale.t("calc.calc.message.time_out")) from e
    else:
        try:
            p = await asyncio.create_subprocess_exec(sys.executable, calc_dir + file,
                                                     input,
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
