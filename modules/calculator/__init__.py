import asyncio
import os
import subprocess
import sys
import time

from core.builtins import Bot
from core.component import module
from core.exceptions import NoReportException
from core.logger import Logger

c = module('calc', developers=[
    'Dianliang233'], desc='{calculator.calc.help.desc}')


@c.command('<math_expression>', options_desc={'+': '{calculator.calc.help.plus}',
                                              '-': '{calculator.calc.help.minus}',
                                              '/': '{calculator.calc.help.multiply}',
                                              '*': '{calculator.calc.help.divide}',
                                              '**': '{calculator.calc.help.power}',
                                              '%': '{calculator.calc.help.modulo}',
                                              '==': '{calculator.calc.help.equal}',
                                              '<=': '{calculator.calc.help.less_equal}',
                                              '>=': '{calculator.calc.help.greater_equal}',
                                              '>>': '{calculator.calc.help.move_right}',
                                              '<<': '{calculator.calc.help.move_left}',
                                              '^': '{calculator.calc.help.xor}',
                                              'not': '{calculator.calc.help.not}',
                                              'is': '{calculator.calc.help.is}',
                                              'randint(x)': '{calculator.calc.help.randint}',
                                              'rand()': '{calculator.calc.help.rand}',
                                              'int()': '{calculator.calc.help.int}',
                                              'float()': '{calculator.calc.help.float}',
                                              'str()': '{calculator.calc.help.str}',
                                              'complex()': '{calculator.calc.help.complex}',
                                              'bool()': '{calculator.calc.help.bool}',
                                              'bin()': '{calculator.calc.help.bin}',
                                              'oct()': '{calculator.calc.help.oct}',
                                              'hex()': '{calculator.calc.help.hex}',
                                              '{calculator.calc.help.more}': 'https://bot.teahouse.team/-/340',
                                              })
async def _(msg: Bot.MessageSession):
    expr = msg.asDisplay().split(' ', 1)[1]
    if sys.platform == 'win32' and sys.version_info.minor < 10:
        try:
            res = subprocess.check_output(
                ['python', os.path.abspath("./modules/calc/calculator.calc.py"), expr], timeout=10, shell=False).decode('utf-8')
            if res[0:6] == 'Result':
                await msg.finish(f'{(expr)} = {res[7:]}')
            else:
                await msg.finish(msg.locale.t("calculator.calc.message.invalid", exp={res[7:]}))
        except subprocess.TimeoutExpired:
            raise NoReportException(msg.locale.t("calculator.calc.message.time_out"))
    else:
        try:
            p = await asyncio.create_subprocess_exec('python', os.path.abspath("./modules/calc/calculator.calc.py"), expr,
                                                     stdout=asyncio.subprocess.PIPE,
                                                     stderr=asyncio.subprocess.PIPE
                                                     )
            try:
                await asyncio.wait_for(p.wait(), timeout=10)
            except asyncio.TimeoutError:
                p.kill()
                raise NoReportException(msg.locale.t("calculator.message.time_out"))
            stdout_data, stderr_data = await p.communicate()
            if p.returncode == 0:
                res = stdout_data.decode('utf-8')

                if res[0:6] == 'Result':
                    await msg.finish(f'{(expr)} = {res[7:]}')
                else:
                    await msg.finish(msg.locale.t("calculator.calc.message.invalid", expr=res[7:]))
            else:
                Logger.error(f'calculator.calc.py exited with code {p.returncode}')
                try:
                    Logger.error(
                        f'calculator.calc.py stderr: {stderr_data.decode("utf-8")}')
                except UnicodeDecodeError:
                    Logger.error(
                        f'calculator.calc.py stderr: {stderr_data.decode("gbk")}')
        except Exception as e:
            raise NoReportException(e)


factor = module('factor', developers=['DoroWolf, Light-Beacon'])

@factor.handle('prime <number> {{calculator.factor.prime.help}}')
async def prime(msg: Bot.MessageSession):
    number_str = msg.parsed_msg.get('<number>')
    start_time = time.time()
    try:
        number = int(number_str)
        if number <= 1:
            await msg.finish(msg.locale.t('calculator.factor.prime.message.error'))
    except ValueError:
        await msg.finish(msg.locale.t('calculator.factor.prime.message.error'))
    n = number
    i = 2
    loopcnt = 0
    primes_list = []
    while i ** 2 <= n:
        loopcnt += 1
        if not(loopcnt % 1000):
            if time.time() - start_time >= 10:
                await msg.finish(msg.locale.t('calculator.message.time_out'))
        if n % i:
            i += 1
        else:
            n //= i
            primes_list.append(str(i))
    prime="*".join(primes_list)
    end_time = time.time()
    running_time = end_time - start_time
    if len(primes_list) == 1:
        result = msg.locale.t("calculator.factor.prime.message.is_prime", num=number)
    else:
        result = f"{number} = {prime}"
    checkpermisson = msg.checkSuperUser()
    if checkpermisson:
        result += '\n' + msg.locale.t("calculator.factor.message.running_time", time=f"{running_time:.2f}")
    await msg.finish(result)
