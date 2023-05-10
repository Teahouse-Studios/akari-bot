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
    if sys.platform == 'win32' and sys.version_info.minor < 10:
        try:
            res = subprocess.check_output(
                [sys.executable, calc_dir + '/calc.py', expr], timeout=10, shell=False)\
                .decode('utf-8')
            if res[0:6] == 'Result':
                if msg.target.senderFrom == "Discord|Client":
                    await msg.finish(f'``{(expr)}`` = {res[7:]}')
                else:
                    await msg.finish(f'{(expr)} = {res[7:]}')
            else:
                await msg.finish(msg.locale.t("calc.calc.message.invalid", expr={res[7:]}))
        except subprocess.TimeoutExpired:
            raise NoReportException(msg.locale.t("calc.calc.message.time_out"))
    else:
        try:
            p = await asyncio.create_subprocess_exec(sys.executable, calc_dir + '/calc.py',
                                                     expr,
                                                     stdout=asyncio.subprocess.PIPE,
                                                     stderr=asyncio.subprocess.PIPE
                                                     )
            try:
                await asyncio.wait_for(p.wait(), timeout=10)
            except asyncio.TimeoutError:
                p.kill()
                raise NoReportException(msg.locale.t("calc.message.time_out"))
            stdout_data, stderr_data = await p.communicate()
            if p.returncode == 0:
                res = stdout_data.decode('utf-8')

                if res[0:6] == 'Result':
                    await msg.finish(f'{(expr)} = {res[7:]}')
                else:
                    await msg.finish(msg.locale.t("calc.calc.message.invalid", expr=res[7:]))
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


factor = module('factor', developers=['DoroWolf, Light-Beacon'])


@factor.handle('prime <number> {{calc.factor.prime.help}}')
async def prime(msg: Bot.MessageSession):
    number_str = msg.parsed_msg.get('<number>')
    start_time = time.time()
    try:
        number = int(number_str)
        if number <= 1:
            await msg.finish(msg.locale.t('calc.factor.prime.message.error'))
    except ValueError:
        await msg.finish(msg.locale.t('calc.factor.prime.message.error'))
    n = number
    i = 2
    loopcnt = 0
    primes_list = []
    while i ** 2 <= n:
        loopcnt += 1
        if not (loopcnt % 1000):
            if time.time() - start_time >= 10:
                await msg.finish(msg.locale.t('calc.message.time_out'))
        if n % i:
            i += 1
        else:
            n //= i
            primes_list.append(str(i))
    primes_list.append(str(n))
    if msg.target.senderFrom == "Discord|Client":
        prime = "\\*".join(primes_list)
    else:
        prime = "*".join(primes_list)
    end_time = time.time()
    running_time = end_time - start_time
    if len(primes_list) == 1:
        result = msg.locale.t("calc.factor.prime.message.is_prime", num=number)
    else:
        result = f"{number} = {prime}"
    checkpermisson = msg.checkSuperUser()
    if checkpermisson:
        result += '\n' + msg.locale.t("calc.factor.message.running_time", time=f"{running_time:.2f}")
    await msg.finish(result)
